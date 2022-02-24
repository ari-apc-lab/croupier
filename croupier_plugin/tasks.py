"""
Copyright (c) 2019 Atos Spain SA. All rights reserved.

This file is part of Croupier.

Croupier is free software: you can redistribute it and/or modify it
under the terms of the Apache License, Version 2.0 (the License) License.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT, IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

See README file for full disclaimer information and LICENSE file for full
license information in the project root.

@author: Javier Carnero
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: javier.carnero@atos.net
@author: Jesus Gorronogoitia
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: jesus.gorronogoitia@atos.net

tasks.py: Holds the plugin tasks
"""
from __future__ import print_function
import os
import sys
import bottle
import configparser
from future import standard_library
from builtins import str
import socket
import traceback
from datetime import datetime
import pytz
import tempfile

import requests
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from croupier_plugin.ssh import SshClient
from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (InfrastructureInterface)
from croupier_plugin.external_repositories.external_repository import (ExternalRepository)
# from croupier_plugin.data_mover.datamover_proxy import (DataMoverProxy)
import croupier_plugin.vault.vault as vault
from croupier_plugin.accounting_client.model.user import (User)
from croupier_plugin.accounting_client.accounting_client import (AccountingClient)
from croupier_plugin.accounting_client.model.resource_consumption_record import (ResourceConsumptionRecord)
from croupier_plugin.accounting_client.model.resource_consumption import (ResourceConsumption, MeasureUnit)
from croupier_plugin.accounting_client.model.reporter import (Reporter, ReporterType)
from croupier_plugin.accounting_client.model.resource import (ResourceType)
import croupier_plugin.data_management.data_management as dm

standard_library.install_aliases()

accounting_client = AccountingClient()


@operation()
def create_vault(address, **kwargs):
    if not address:
        ctx.logger.info("No address provided, getting vault address from croupier's config file")
        address = getVaultAddressFromConfiguration()
    ctx.instance.runtime_properties['address'] = address if address.startswith('http') else 'http://' + address


def getVaultAddressFromConfiguration():
    config = configparser.RawConfigParser()
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/Croupier.cfg'
    config.read(config_file)
    try:
        address = config.get('Vault', 'vault_address')
        if address is None:
            raise NonRecoverableError('Could not find Vault address in the croupier config file.')
        return address
    except configparser.NoSectionError:
        raise NonRecoverableError('Could not find the Vault section in the croupier config file.')


@operation()
def download_vault_credentials(token, user, cubbyhole, **kwargs):
    address = ctx.target.instance.runtime_properties['address']

    try:
        if not cubbyhole and not user:
            raise NonRecoverableError("If cubbyhole is false, a user must be provided to download Vault credentials")

        if 'credentials' in ctx.source.node.properties:
            host = ctx.source.node.properties['endpoint'] if 'endpoint' in ctx.source.node.properties else \
                ctx.source.node.properties['credentials']['host']
            downloaded_credentials = vault.download_credentials(host, token, user, address, cubbyhole)
            if downloaded_credentials:
                credentials = ctx.source.node.properties['credentials']
                credentials.update(downloaded_credentials)
                ctx.source.instance.runtime_properties['credentials'] = credentials
                ctx.logger.info("SSH credentials downloaded from Vault for host {0}.".format(host))
            else:
                ctx.logger.info("Using provided ssh credentials.")


        if 'keycloak_credentials' in ctx.source.node.properties:
            keycloak_credentials = vault.download_credentials('keycloak', token, user, address, cubbyhole)
            if keycloak_credentials:
                ctx.source.instance.runtime_properties['keycloak_credentials'] = keycloak_credentials
                ctx.logger.info("Keycloak credentials downloaded from Vault for user {0}.".format(user))
            else:
                ctx.logger.info("Using provided credentials.")

    except Exception as exp:
        ctx.logger.error("Failed trying to get credentials from Vault for user: {0} because of error {1}".
                         format(user, str(exp)))
        raise NonRecoverableError("Failed trying to get credentials from Vault")


def findVaultNode(node_templates):
    for node in node_templates:
        if node['type'] == 'croupier.nodes.Vault':
            return node
    return None


@operation
def configure_data_source(**kwargs):
    # Configure DataSource located_at
    ctx.logger.info('Configuring data source: ' + ctx.source.node.name)
    located_at = {
        "endpoint": ctx.target.node.properties['endpoint']
        if 'endpoint' in ctx.target.node.properties else ctx.target.node.properties['credentials']['host'],
        "internet_access": ctx.target.node.properties['internet_access'],
        "supported_protocols": ctx.target.node.properties['supported_protocols']
        if "supported_protocols" in ctx.target.node.properties else None,
        "credentials": ctx.target.instance.runtime_properties['credentials']
        if "credentials" in ctx.target.instance.runtime_properties else ctx.target.node.properties['credentials'],
        "workdir": ctx.target.instance.runtime_properties['workdir']
        if 'workdir' in ctx.target.instance.runtime_properties else None}
    ctx.source.instance.runtime_properties['located_at'] = located_at
    ctx.logger.info("Data source infrastructure {0} configured as location for data source {1}"
                    .format(ctx.target.node.name, ctx.source.node.name))


@operation
def configure_data_transfer(**kwargs):
    # Configure Data Transfer from_source
    ctx.logger.info('Configuring data transfer: ' + ctx.node.name)
    from_source_rel = ctx.instance.relationships[0] if ctx.instance.relationships[0].type == 'from_source' \
        else ctx.instance.relationships[1]
    to_target_rel = ctx.instance.relationships[0] if ctx.instance.relationships[0].type == 'to_target' \
        else ctx.instance.relationships[1]

    from_source_node = from_source_rel.target.node
    from_source_instance = from_source_rel.target.instance

    to_target_node = to_target_rel.target.node
    to_target_instance = to_target_rel.target.instance

    from_source = {
        "name": from_source_node.name,
        "type": from_source_node.type,
        "filepath": from_source_node.properties['filepath']
        if "filepath" in from_source_node.properties else None,
        "resource": from_source_instance.runtime_properties['resource']
            if 'resource' in from_source_instance.runtime_properties else (from_source_node.properties['resource']
            if 'resource' in from_source_node.properties else None),
        "located_at": from_source_instance.runtime_properties['located_at']
        if "located_at" in from_source_instance.runtime_properties else None}
    ctx.instance.runtime_properties['from_source'] = from_source

    to_target = {
        "name": to_target_node.name,
        "type": to_target_node.type,
        "filepath": to_target_node.properties['filepath']
        if "filepath" in to_target_node.properties else None,
        "resource": to_target_instance.runtime_properties['resource']
            if 'resource' in to_target_instance.runtime_properties else (to_target_node.properties['resource']
            if "resource" in to_target_node.properties else None),
        "located_at": to_target_instance.runtime_properties['located_at']
        if "located_at" in to_target_instance.runtime_properties else None}
    ctx.instance.runtime_properties['to_target'] = to_target

    ctx.logger.info("Data Source {0} configured".format(ctx.node.name))


def containsDTInstance(dt, dt_instances):
    for instance in dt_instances:
        if instance['id'] == dt['id']:
            return True
    return False


@operation
def configure_dt_ds_relationship(**kwargs):
    ctx.logger.info('Configuring data transfer source')
    dt_instance = {
        "id": ctx.source.instance.id,
        "transfer_protocol": ctx.source.node.properties['transfer_protocol'],
        "from_source": ctx.source.instance.runtime_properties['from_source'],
        "to_target": ctx.source.instance.runtime_properties['to_target']
    }

    if 'dt_instances' not in ctx.target.instance.runtime_properties:
        ctx.target.instance.runtime_properties['dt_instances'] = []

    if not containsDTInstance(dt_instance, ctx.target.instance.runtime_properties['dt_instances']):
        ctx.target.instance.runtime_properties['dt_instances'].append(dt_instance)


@operation
def preconfigure_interface(
        credentials,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Get interface config from infrastructure """

    if not simulate:
        credentials_modified = False

        if 'ip' in ctx.target.instance.runtime_properties:
            ctx.logger.info('Preconfiguring infrastructure interface for {0}'.
                            format(ctx.target.instance.runtime_properties['ip']))
            credentials['host'] = \
                ctx.target.instance.runtime_properties['ip']
            credentials_modified = True

        for rel in ctx.target.instance.relationships:  # server relationships
            node = rel.target.node
            instance = rel.target.instance
            if node.type == 'cloudify.openstack.nodes.KeyPair':
                # take private key from openstack
                if 'private_key_path' in node.properties:
                    with open(node.properties['private_key_path'], 'r') \
                            as keyfile:
                        private_key = keyfile.read()
                        credentials['private_key'] = private_key
                        credentials_modified = True
            elif node.type == 'cloudify.openstack.nodes.FloatingIP':
                # take public ip from openstack
                if 'floating_ip_address' in instance.runtime_properties:
                    credentials['host'] = \
                        instance.runtime_properties['floating_ip_address']
                    credentials_modified = True

        if credentials_modified:
            ctx.source.instance.runtime_properties['credentials'] = \
                credentials

        if 'networks' in ctx.source.instance.runtime_properties:
            ctx.source.instance.runtime_properties['networks'] = \
                ctx.target.instance.runtime_properties['networks']
        else:
            ctx.source.instance.runtime_properties['networks'] = {}
        ctx.logger.info('..preconfigured ')
    else:
        ctx.logger.warning('Infrastructure Interface simulated')


@operation
def configure_execution(
        config,
        credentials,
        base_dir,
        workdir_prefix,
        monitoring_options,
        accounting_options,
        recurring_workflow,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Creates the working directory for the execution """
    # Registering accounting and monitoring options
    ctx.instance.runtime_properties['monitoring_options'] = monitoring_options
    ctx.instance.runtime_properties['accounting_options'] = accounting_options
    ctx.instance.runtime_properties['infrastructure_host'] = credentials['host']
    if recurring_workflow and "recurring" not in kwargs:
        ctx.logger.info(
            "Configuration of infrastructure interfaces in the case of recurring workflows happens during croupier_configure")
    elif not recurring_workflow and "recurring" in kwargs and kwargs["recurring"]:
        pass
    elif not simulate:
        ctx.logger.info('Connecting to infrastructure interface {0}'.format(ctx.instance.id))
        if 'infrastructure_interface' not in config:
            raise NonRecoverableError(
                "'infrastructure_interface' key missing on config")
        interface_type = config['infrastructure_interface']
        ctx.logger.info(' - manager: {interface_type}'.format(interface_type=interface_type))
        wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir_prefix)
        if not wm:
            raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")

        if 'credentials' in ctx.instance.runtime_properties:
            credentials = ctx.instance.runtime_properties['credentials']
        try:
            client = SshClient(credentials)
        except Exception as exp:
            ctx.logger.error('Error Connecting to infrastructure interface {0} with error {1}'
                             .format(ctx.instance.id, str(exp)))
            raise NonRecoverableError(
                "Failed trying to connect to infrastructure interface: " + str(exp))

        # TODO: use command according to wm
        _, exit_code = client.execute_shell_command('uname', wait_result=True)

        if exit_code != 0:
            client.close_connection()
            raise NonRecoverableError("Failed executing on the infrastructure: exit code " + str(exit_code))
        ctx.instance.runtime_properties['login'] = exit_code == 0

        # Initialize Scheduler (required by some but not all schedulers: e.g. PyCOMPSs)
        wm.initialize(credentials, client)

        prefix = workdir_prefix if workdir_prefix else ctx.blueprint.name
        workdir = wm.create_new_workdir(client, base_dir, prefix)
        client.close_connection()
        if workdir is None:
            raise NonRecoverableError("failed to create the working directory, base dir: " + base_dir)
        ctx.instance.runtime_properties['workdir'] = workdir

        # Register Croupier instance in Accounting if not done before
        if accounting_client.report_to_accounting:
            register_orchestrator_instance_accounting()

        ctx.logger.info('..infrastructure ready to be used on ' + workdir)
    else:
        ctx.logger.info(' - [simulation]..')
        ctx.instance.runtime_properties['login'] = True
        ctx.instance.runtime_properties['workdir'] = "simulation"
        ctx.logger.warning('Infrastructure Interface connection simulated')


@operation
def cleanup_execution(
        config,
        credentials,
        skip,
        simulate,
        **kwargs):  # pylint: disable=W0613

    """ Cleans execution working directory """
    if skip:
        return

    ctx.logger.info('Cleaning up...')
    if not simulate:
        workdir = ctx.instance.runtime_properties['workdir']
        interface_type = config['infrastructure_interface']
        wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir)
        if not wm:
            raise NonRecoverableError(
                "Infrastructure Interface '" +
                interface_type +
                "' not supported.")

        if 'credentials' in ctx.instance.runtime_properties:
            credentials = ctx.instance.runtime_properties['credentials']
        client = SshClient(credentials)
        client.execute_shell_command(
            'rm -r ' + workdir,
            wait_result=True)
        client.close_connection()

        ctx.logger.info('..all clean.')
    else:
        ctx.logger.warning('clean up simulated.')


@operation
def create_monitor(address, **kwargs):
    if not address:
        ctx.logger.info(
            "No HPC Exporter address provided. Using address set in croupier installation's config file")
        config = configparser.RawConfigParser()
        config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/Croupier.cfg'
        config.read(config_file)
        try:
            address = config.get('Monitoring', 'hpc_exporter_address')
            if address is None:
                ctx.logger.error(
                    'Could not find HPC Exporter address in the croupier config file. No HPC Exporter will be activated')
                return
        except configparser.NoSectionError:
            ctx.logger.error(
                'Could not find Monitoring section in the croupier config file. No HPC Exporter will be activated')
            return

    monitoring_id = ctx.deployment.id
    ctx.logger.info("Monitoring_id generated: " + monitoring_id)
    ctx.instance.runtime_properties["monitoring_id"] = monitoring_id

    ctx.instance.runtime_properties["hpc_exporter_address"] = address if address.startswith("http") \
        else "http://" + address


@operation
def preconfigure_interface_monitor(**kwargs):
    ctx.source.instance.runtime_properties["monitoring_id"] = ctx.target.instance.runtime_properties["monitoring_id"]
    hpc_exporter_address = ctx.target.instance.runtime_properties["hpc_exporter_address"]
    ctx.source.instance.runtime_properties["hpc_exporter_address"] = hpc_exporter_address


@operation
def start_monitoring_hpc(
        config_infra,
        credentials,
        monitoring_options,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Starts monitoring using the HPC Exporter """

    if not simulate and "hpc_exporter_address" in ctx.instance.runtime_properties and \
            ctx.instance.runtime_properties["hpc_exporter_address"]:
        monitoring_id = ctx.instance.runtime_properties["monitoring_id"]
        hpc_exporter_address = ctx.instance.runtime_properties["hpc_exporter_address"]
        ctx.logger.info('Creating Collector in HPC Exporter...')
        if 'credentials' in ctx.instance.runtime_properties:
            credentials = ctx.instance.runtime_properties['credentials']
        infrastructure_interface = config_infra['infrastructure_interface'].lower()
        infrastructure_interface = "pbs" if infrastructure_interface == "torque" else infrastructure_interface
        monitor_period = monitoring_options["monitor_period"] if "monitor_period" in monitoring_options else 30

        deployment_label = monitoring_options["deployment_label"] if "deployment_label" in monitoring_options \
            else ctx.deployment.id
        hpc_label = monitoring_options["hpc_label"] if "hpc_label" in monitoring_options else ctx.node.name
        only_jobs = monitoring_options["only_jobs"] if "only_jobs" in monitoring_options else False

        if (infrastructure_interface != "slurm") and (infrastructure_interface != "pbs"):
            ctx.logger.warning("HPC Exporter doesn't support '{0}' interface. Collector will not be created."
                               .format(infrastructure_interface))
            ctx.instance.runtime_properties["hpc_exporter_address"] = None
            return

        payload = {
            "host": credentials["host"],
            "scheduler": infrastructure_interface,
            "scrape_interval": monitor_period,
            "deployment_label": deployment_label,
            "monitoring_id": monitoring_id,
            "hpc_label": hpc_label,
            "only_jobs": only_jobs,
            "ssh_user": credentials["user"]
        }

        if "password" in credentials and credentials["password"]:
            payload["ssh_password"] = credentials["password"]
        else:
            payload["ssh_pkey"] = credentials["private_key"]

        url = hpc_exporter_address + '/collector'
        ctx.logger.info("Creating collector in " + str(url))
        response = requests.request("POST", url, json=payload)

        if not response.ok:
            ctx.logger.error("Failed to start node monitor: {0}: {1}".format(response.status_code, response.content))
            return
        ctx.logger.info("Monitor started for HPC: {0} ({1})".format(credentials["host"], hpc_label))
    elif simulate:
        ctx.logger.warning('monitor simulated')
    else:
        ctx.logger.warning("No HPC Exporter selected for node {0}. Won't create a collector in any HPC Exporter for it."
                           .format(ctx.node.name))


@operation
def stop_monitoring_hpc(
        credentials,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Removes the HPC Exporter's collector """

    if "hpc_exporter_address" in ctx.instance.runtime_properties and \
            ctx.instance.runtime_properties["hpc_exporter_address"]:
        hpc_exporter_address = ctx.instance.runtime_properties["hpc_exporter_address"]
        ctx.logger.info('Removing collector from HPC Exporter...')

        if not simulate:
            host = credentials['host']
            monitoring_id = ctx.instance.runtime_properties["monitoring_id"]
            url = hpc_exporter_address + '/collector'

            payload = {
                "host": host,
                "monitoring_id": monitoring_id
            }

            response = requests.request("DELETE", url, json=payload)

            if not response.ok:
                ctx.logger.error("Failed to remove collector from HPC Exporter: {0}".format(response.status_code))
                return
            ctx.logger.info("Monitor stopped for HPC: {0}".format(host))
        else:
            ctx.logger.warning('monitor removal simulated')
    else:
        ctx.logger.info("No collector to delete for node {0}".format(ctx.node.name))


@operation
def preconfigure_task(
        config,
        credentials,
        job_prefix,
        monitoring_options,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Match the job with its credentials """
    ctx.logger.info('Preconfiguring job {0}'.format(ctx.source.instance.id))

    if "recurring" not in kwargs:
        if 'credentials' not in ctx.target.instance.runtime_properties:
            ctx.source.instance.runtime_properties['credentials'] = credentials
        else:
            ctx.source.instance.runtime_properties['credentials'] = ctx.target.instance.runtime_properties['credentials']
        if not ctx.target.node.properties['recurring_workflow']:
            ctx.source.instance.runtime_properties['workdir'] = ctx.target.instance.runtime_properties['workdir']
        ctx.source.instance.runtime_properties['monitoring_options'] = monitoring_options
        ctx.source.instance.runtime_properties['infrastructure_interface'] = config['infrastructure_interface']
        ctx.source.instance.runtime_properties['reservation_deletion_path'] = config['reservation_deletion_path']
        ctx.source.instance.runtime_properties['timezone'] = config['country_tz']
        ctx.source.instance.runtime_properties['simulate'] = simulate
        ctx.source.instance.runtime_properties['job_prefix'] = job_prefix

        if 'hpc_exporter_address' in ctx.target.instance.runtime_properties and \
                ctx.target.instance.runtime_properties['hpc_exporter_address']:
            ctx.source.instance.runtime_properties['hpc_exporter_address'] = \
                ctx.target.instance.runtime_properties['hpc_exporter_address']
            ctx.source.instance.runtime_properties['monitoring_id'] = \
                ctx.target.instance.runtime_properties['monitoring_id']

    elif ctx.target.node.properties['recurring_workflow'] and kwargs["recurring"]:
        ctx.source.instance.runtime_properties['workdir'] = ctx.target.instance.runtime_properties['workdir']


@operation
def configure_job(
        job_options,
        deployment,
        skip_cleanup,
        **kwargs):  # pylint: disable=W0613
    """Bootstrap a job with a script that receives SSH credentials as input"""
    if not deployment:
        return

    if 'reservation' in job_options:
        reservation_id = job_options['reservation']
        if 'recurrent_reservation' in job_options and job_options['recurrent_reservation']:
            timezone = ctx.instance.runtime_properties['timezone']
            reservation_id = datetime.now(tz=pytz.timezone(timezone)).strftime(reservation_id)
            job_options['reservation'] = reservation_id
        ctx.instance.runtime_properties['reservation'] = reservation_id
        ctx.logger.info('Using reservation ID ' + reservation_id)
    if 'recurring_workflow' in ctx.instance.runtime_properties and ctx.instance.runtime_properties['recurring_workflow'] \
            and 'recurring_bootstrap' in deployment and deployment['recurring_bootstrap'] and "recurring" not in kwargs:
        ctx.logger.info('Recurring Bootstrap selected, job bootstrap will happen during croupier_configure')
        return

    ctx.logger.info('Bootstraping job {0}'.format(ctx.instance.id))
    simulate = ctx.instance.runtime_properties['simulate']

    if not simulate and 'bootstrap' in deployment and deployment['bootstrap']:
        inputs = deployment['inputs'] if 'inputs' in deployment else []
        credentials = ctx.instance.runtime_properties['credentials']
        workdir = ctx.instance.runtime_properties['workdir']
        name = "bootstrap_" + ctx.instance.id + ".sh"
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        bootstrap = deployment['bootstrap']
        execution_in_hpc = deployment['hpc_execution']
        if deploy_job(bootstrap, inputs, execution_in_hpc, credentials, interface_type, workdir, name,
                      ctx.logger, skip_cleanup):
            ctx.logger.info('..job bootstraped')
        else:
            ctx.logger.error('Job not bootstraped')
            raise NonRecoverableError("Bootstrap failed")
    else:
        if 'bootstrap' in deployment and deployment['bootstrap']:
            ctx.logger.warning('..bootstrap simulated')
        else:
            ctx.logger.info('..nothing to bootstrap')

    #  Deploy job if WM scheduler is PyCOMPSs
    interface_type = ctx.instance.runtime_properties['infrastructure_interface']
    if interface_type == "PYCOMPSS":
        credentials = ctx.instance.runtime_properties['credentials']
        workdir = ctx.instance.runtime_properties['workdir']
        wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir)
        if not wm:
            raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")
        ssh_client = SshClient(credentials)
        job_options["job_id"] = ctx.instance.id
        wm.deploy_app(job_options, workdir, ssh_client)


@operation
def revert_job(deployment, skip_cleanup, **kwargs):  # pylint: disable=W0613
    """Revert a job using a script that receives SSH credentials as input"""
    if not deployment:
        return

    ctx.logger.info('Reverting job {0}'.format(ctx.instance.id))
    try:
        simulate = ctx.instance.runtime_properties['simulate']

        if not simulate and 'revert' in deployment and deployment["revert"]:
            inputs = deployment['inputs'] if 'inputs' in deployment else []
            credentials = ctx.instance.runtime_properties['credentials']
            workdir = ctx.instance.runtime_properties['workdir']
            name = "revert_" + ctx.instance.id + ".sh"
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            revert = deployment['revert']
            execution_in_hpc = deployment['hpc_execution']
            if deploy_job(revert, inputs, execution_in_hpc, credentials, interface_type, workdir, name, ctx.logger, skip_cleanup):
                ctx.logger.info('..job reverted')
            else:
                ctx.logger.error('Job not reverted')
                raise NonRecoverableError("Revert failed")
        else:
            if 'revert' in deployment and deployment["revert"]:
                ctx.logger.warning('..revert simulated')
            else:
                ctx.logger.info('..nothing to revert')
    except KeyError:
        # The job wasn't configured properly, so there was no bootstrap
        ctx.logger.warning('Job {0} was not reverted as it was not configured'.format(ctx.instance.id))


def deploy_job(script, inputs, execution_in_hpc, credentials, interface_type, workdir, name, logger,
               skip_cleanup):  # pylint: disable=W0613
    """ Exec a deployment job script that receives SSH credentials as input """

    wm = InfrastructureInterface.factory(interface_type, logger, workdir)
    if not wm:
        raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")

    # Execute the script and manage the output
    success = False
    if execution_in_hpc:  # execute the deployment script in target hpc
        success = remote_deploy(credentials, inputs, logger, name, script, skip_cleanup, wm, workdir)
    else:  # execute the deployment script in local Croupier server
        success = local_deploy(credentials, inputs, logger, name, script, skip_cleanup, wm, workdir)

    return success


def local_deploy(credentials, inputs, logger, name, script, skip_cleanup, wm, workdir):
    #  Inject credentials as input is deployment script.
    #  Execute script in forked process, wait for result
    success = False
    #  Save deploy script in temporary folder
    deploy_script_content = script if script[0] == '#' else ctx.get_resource(script)
    with tempfile.NamedTemporaryFile(suffix='.sh') as temp_file:
        temp_file.write(deploy_script_content)
        temp_file.flush()
        deploy_script_filepath = temp_file.name
        #  Inject HPC credentials to script invocation: ./script.sh -u <user> -k <path_to_pkey> -h <host> -p <passwd>
        deploy_cmd = 'sh ' + deploy_script_filepath + " -u {user} -h {host}".format(
            user=credentials["user"], host=credentials["host"]
        )
        if "password" in credentials and len(credentials["password"]) > 0:
            deploy_cmd += " -p " + credentials["password"]

        private_key = None
        if "private_key" in credentials and len(credentials["private_key"]) > 0:
            # Save key in temporary file
            with tempfile.NamedTemporaryFile(delete=False) as key_file:
                key_file.write(bytes(credentials["private_key"], 'utf-8'))
                key_file.flush()
                private_key = key_file.name
            deploy_cmd += " -k " + private_key

        #  Inject deployment inputs
        deploy_cmd = inject_deploy_inputs(deploy_cmd, inputs)

        #  Execute deploy script
        try:
            logger.info('deploying job with script: {}'.format(script))
            cmd_output = os.popen(deploy_cmd)
            cmd_msg = cmd_output.read()
            exit_code = cmd_output.close()
            if exit_code is not None:
                logger.warning("job deploying failed with exit code {code} and msg: {msg}"
                               .format(code=str(exit_code), msg=cmd_msg))
            else:
                success = True
        finally:
            #  Clean up
            if private_key and os.path.exists(private_key):
                # Remove key temporary file
                os.remove(private_key)

    return success


def remote_deploy(credentials, inputs, logger, name, script, skip_cleanup, wm, workdir):
    success = False
    client = SshClient(credentials)
    script_content = script if script[0] == '#' else ctx.get_resource(script)
    if wm.create_shell_script(client, name, script_content):
        call = "./" + name
        call = inject_deploy_inputs(call, inputs)
        _, exit_code = client.execute_shell_command(call, workdir=workdir, wait_result=True)
        if exit_code != 0:
            logger.warning("failed to deploy job: call '" + call + "', exit code " + str(exit_code))
        else:
            success = True

        if not skip_cleanup:
            if not client.execute_shell_command("rm " + name, workdir=workdir):
                logger.warning("failed removing bootstrap script")
    client.close_connection()
    return success


def inject_deploy_inputs(call, inputs):
    for dinput in inputs:
        str_input = str(dinput)
        if ('\n' in str_input or ' ' in str_input) and str_input[0] != '"':
            call += ' "' + str_input + '"'
        else:
            call += ' ' + str_input + ' ' + inputs[str_input]
    return call


@operation
def send_job(job_options, **kwargs):  # pylint: disable=W0613
    """ Sends a job to the infrastructure interface """
    ctx.logger.info('Executing send_job task {0}'.format(ctx.instance.id))
    simulate = ctx.instance.runtime_properties['simulate']

    name = kwargs['name']
    is_singularity = 'croupier.nodes.SingularityJob' in ctx.node.type_hierarchy

    if 'reservation' in ctx.instance.runtime_properties:
        job_options['reservation'] = ctx.instance.runtime_properties['reservation']

    if not simulate:
        # Process data flow for inputs in this job
        dm.processDataTransfer(ctx.instance, ctx.logger, 'input')

        # Prepare HPC interface to send job
        workdir = ctx.instance.runtime_properties['workdir']
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        client = SshClient(ctx.instance.runtime_properties['credentials'])

        wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir)
        if not wm:
            client.close_connection()
            raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")
        context_vars = {
            'CFY_EXECUTION_ID': ctx.execution_id,
            'CFY_JOB_NAME': name
        }
        ctx.logger.info('Submitting the job {0}'.format(ctx.instance.id))

        try:
            job_options["workdir"] = workdir
            jobid = wm.submit_job(client, name, job_options, is_singularity, ctx, context_vars)
        except Exception as ex:
            ctx.logger.error('Job {0} could not be submitted because error {1}'.format(ctx.instance.id, str(ex)))
            raise ex
        client.close_connection()
    else:
        ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')
        jobid = "Simulated"

    if jobid:
        ctx.logger.info('Job ' + name + ' (' + ctx.instance.id + ') sent. Jobid: ' + jobid)
    else:
        ctx.logger.error(
            'Job ' + name + ' (' + ctx.instance.id + ') not sent.')
        raise NonRecoverableError(
            'Job ' + name + ' (' + ctx.instance.id + ') not sent.')

    ctx.instance.runtime_properties['job_name'] = name
    ctx.instance.runtime_properties['job_id'] = jobid
    hpc_exporter_address = ctx.instance.runtime_properties['hpc_exporter_address'] \
        if 'hpc_exporter_address' in ctx.instance.runtime_properties else None
    if hpc_exporter_address:
        monitor_job(jobid,
                    hpc_exporter_address,
                    ctx.instance.runtime_properties['monitoring_id'],
                    ctx.instance.runtime_properties['credentials']['host'])
    ctx.instance.update()


@operation
def delete_reservation(**kwargs):
    name = kwargs["name"]
    if not ('reservation' in ctx.instance.runtime_properties) and not \
            ('reservation_deletion_path' in ctx.instance.runtime_properties):
        ctx.logger.warning("No reservation found for job " + name)
        return
    reservation_id = ctx.instance.runtime_properties['reservation']
    interface_type = ctx.instance.runtime_properties['infrastructure_interface']
    client = SshClient(ctx.instance.runtime_properties['credentials'])
    deletion_path = ctx.instance.runtime_properties['reservation_deletion_path']
    wm = InfrastructureInterface.factory(interface_type, ctx.logger, '')
    if not wm:
        client.close_connection()
        raise NonRecoverableError(
            "Infrastructure Interface '" +
            interface_type +
            "' not supported.")

    ctx.logger.info('Submitting the job ...')

    try:
        ok = wm.delete_reservation(
            client,
            reservation_id,
            deletion_path)
    except Exception as ex:
        ctx.logger.error('Reservation could not be deleted because error: ' + str(ex))
        client.close_connection()
        return
    client.close_connection()

    if ok:
        ctx.logger.info('Reservation with ID {0} deleted successfully'.format(reservation_id))
    else:
        ctx.logger.warning('Reservation with ID {0} could not be deleted, it might have already been deleted'
                           .format(reservation_id))


@operation
def cleanup_job(job_options, skip, **kwargs):  # pylint: disable=W0613
    """Clean the aux files of the job"""
    if skip:
        return

    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, so no cleanup needed
        ctx.logger.error('Job {0} was not cleaned up as it was not configured'.format(ctx.instance.id))
        return

    try:
        name = kwargs['name']
        if not simulate:
            is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
                type_hierarchy
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

            wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir)
            if not wm:
                client.close_connection()
                raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")
            is_clean = wm.clean_job_aux_files(client, name, is_singularity)

            client.close_connection()
        else:
            ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')
            is_clean = True

        if is_clean:
            ctx.logger.info('Job ' + name + ' (' + ctx.instance.id + ') cleaned.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id + ') not cleaned.')
    except Exception as exp:
        ctx.logger.error(
            'Error happened when trying to clean up:' + '\n' + traceback.format_exc() + '\n' + str(exp))


@operation
def stop_job(job_options, **kwargs):  # pylint: disable=W0613
    """ Stops a job in the infrastructure """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, no need to be stopped
        ctx.logger.error('Job {0} was not stopped as it was not configured properly.'.format(ctx.instance.id))
        return

    try:
        name = kwargs['name']
        is_singularity = 'croupier.nodes.SingularityJob' in ctx.node.type_hierarchy

        if not simulate:
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

            wm = InfrastructureInterface.factory(interface_type, ctx.logger, workdir)
            if not wm:
                client.close_connection()
                raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")
            is_stopped = wm.stop_job(client, name, job_options, is_singularity)

            client.close_connection()
        else:
            ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')
            is_stopped = True

        if is_stopped:
            ctx.logger.info('Job ' + name + ' (' + ctx.instance.id + ') stopped.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id + ') not stopped.')
            raise NonRecoverableError('Job ' + name + ' (' + ctx.instance.id + ') not stopped.')
    except Exception as exp:
        ctx.logger.error('Something happened when trying to stop job:'
                         + '\n' + traceback.format_exc() + '\n' + str(exp))


@operation
def publish(publish_list, **kwargs):
    """ Publish the job outputs """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, no need to publish
        ctx.logger.warning(
            'Job {0} outputs where not published as the job was not configured properly.'.format(ctx.instance.id))
        return

    try:
        name = kwargs['name']
        audit = kwargs['audit']
        published = True
        if not simulate:
            # Process data flow for outputs in this job
            dm.processDataTransfer(ctx.instance, ctx.logger, 'output')

            workdir = ctx.instance.runtime_properties['workdir']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

            hpc_interface = ctx.instance.relationships[0].target.instance
            audit["cput"] = \
                convert_cput(audit["cput"], job_id=name, workdir=workdir, ssh_client=client, logger=ctx.logger) \
                    if audit is not None and "cput" in audit and audit["cput"] else 0
            # Report metrics to Accounting component
            if accounting_client.report_to_accounting:
                username = None
                if hpc_interface is not None and "accounting_options" in hpc_interface.runtime_properties:
                    accounting_options = hpc_interface.runtime_properties["accounting_options"]
                    username = accounting_options["reporting_user"]
                if "croupier_reporter_id" in hpc_interface.runtime_properties:
                    croupier_reporter_id = hpc_interface.runtime_properties['croupier_reporter_id']
                    report_metrics_to_accounting(audit, job_id=name, username=username,
                                                 croupier_reporter_id=croupier_reporter_id, logger=ctx.logger)
                else:
                    ctx.logger.error(
                        'Consumed resources by workflow {workflow_id} could not be reported to Accounting: '
                        'Croupier instance not registered in Accounting'.format(workflow_id=ctx.workflow_id))

            for publish_item in publish_list:
                if not published:
                    break
                exrep = ExternalRepository.factory(publish_item)
                if not exrep:
                    client.close_connection()
                    raise NonRecoverableError(
                        "External repository '" +
                        publish_item['dataset']['type'] +
                        "' not supported.")
                published = exrep.publish(client, ctx.logger, workdir)

            client.close_connection()
        else:
            ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')

        if published:
            ctx.logger.info('Job ' + name + ' (' + ctx.instance.id + ') published.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id + ') not published.')
            raise NonRecoverableError('Job ' + name + ' (' + ctx.instance.id + ') not published.')
    except Exception as exp:
        ctx.logger.error('Cannot publish:\n' + traceback.format_exc() + '\n' + str(exp))


@operation
def ecmwf_vertical_interpolation(query, keycloak_credentials, credentials, cloudify_address, server_port, **kwargs):

    if 'recurring_workflow' in ctx.instance.runtime_properties and ctx.instance.runtime_properties['recurring_workflow'] \
            and "recurring" not in kwargs:
        ctx.logger.info('Recurring workflow, ecmwf data will be generated during croupier_configure')
        return
    ALGORITHMS = ["sequential", "semi_parallel", "fully_parallel"]
    server_host = cloudify_address if cloudify_address else requests.get('https://api.ipify.org').text
    if "keycloak_credentials" in ctx.instance.runtime_properties:
        keycloak_credentials = ctx.instance.runtime_properties["keycloak_credentials"]
    if "credentials" in ctx.instance.runtime_properties:
        credentials = ctx.instance.runtime_properties["credentials"]
    ctx.logger.info('IP is: ' + server_host)

    arguments = {"notify": "http://" + server_host + ":" + str(server_port) + "/ready",
                 "user_name": keycloak_credentials["user"],
                 "password": keycloak_credentials["password"],
                 "params": query["params"],
                 "area": query["area"],
                 "max_step": query["max_step"],
                 "ensemble": query["ensemble"],
                 "input": query["input"],
                 "members": query["members"],
                 "keep_input": query["keep_input"],
                 "collection": query["collection"],
                 "algorithm": query["algorithm"] if "algorithm" in query and query[
                     "algorithm"] in ALGORITHMS else ""}

    if query["date"]:
        arguments["date"] = query["date"]
        arguments["time"] = query["time"]
    try:
        client = SshClient(credentials)
    except Exception as e:
        ctx.logger.error("There was an error trying to connect to ECMWF's VM: {0}".format(str(e)))
        raise
    command = "cd cloudify && source /opt/anaconda3/etc/profile.d/conda.sh && conda activate && " \
              "nohup python3 interpolator.py"

    for arg in arguments:
        command += " --" + arg + " " + str(arguments[arg]) if arguments[arg] is not "" else ""

    # out_file = str(time())
    out_file = "/dev/null"
    command += " > " + out_file + " 2>&1 & disown"

    client.execute_shell_command(command)
    client.close_connection()

    # Waits for confirmation that retrieval of data is finished and ready to upload to CKAN
    ctx.logger.info('Waiting for response from ECMWF')

    @bottle.post('/ready')
    def ready():
        try:
            ctx.logger.info('Response received from ECMWF')
            data = bottle.request.json
            if "error_msg" in data and "stdout" in data:
                ctx.logger.error(
                    "There was an error reported by ECMWF:\nError_msg:" + data["error_msg"] + "\nOutput:" + data[
                        "stdout"])
                return 200
            elif "file" in data and "stdout" in data:
                ctx.instance.runtime_properties['resource'] = data["file"]
                ctx.logger.info("Process completed, stdout:\n" + data["stdout"])
                ctx.logger.info("CKAN URL: " + data["file"])
                return 200
            else:
                ctx.logger.error(str(data))
                ctx.logger.error("Non valid response from ECMWF received")
        except Exception as e:
            ctx.logger.error("There was an error handling response from ECMWF: " + str(e))
        finally:
            sys.stderr.close()

    try:
        ctx.logger.info("Listening in: " + server_host + ":" + str(server_port))
        bottle.run(host='0.0.0.0', port=server_port)
    except ValueError:
        pass

def get_hours(cput):
    return int(cput[:cput.index(':')])


def get_minutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def get_seconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def parse_hours(cput):
    hours = get_hours(cput) + get_minutes(cput) / 60.0 + get_seconds(cput) / 3600.0
    return hours


def monitor_job(jobid, hpc_exporter_entrypoint, deployment_id, host):
    url = hpc_exporter_entrypoint + "/job"
    payload = {
        "monitoring_id": deployment_id,
        "host": host,
        "job_id": jobid
    }
    requests.post(url, json=payload)


def register_orchestrator_instance_accounting():
    hostname = socket.gethostname()
    reporter_name = 'croupier@' + hostname

    try:
        reporter = accounting_client.get_reporter_by_name(reporter_name)
        ctx.instance.runtime_properties['croupier_reporter_id'] = reporter.id
        ctx.logger.info('Registered Croupier reporter in Accounting with id {}'.format(reporter.id))
    except Exception:
        # Croupier not registered in Accounting
        try:
            ip = requests.get('https://api.ipify.org').text
            reporter = Reporter(reporter_name, ip, ReporterType.Orchestrator)
            reporter = accounting_client.add_reporter(reporter)
            ctx.instance.runtime_properties['croupier_reporter_id'] = reporter.id
        except Exception as err:
            ctx.logger.warning(
                'Croupier instance could not be registered into Accounting, raising an error: {}'.format(str(err)))


def convert_cput(cput, job_id, workdir, ssh_client, logger):
    processors_per_node = read_processors_per_node(job_id, workdir, ssh_client, logger)
    if processors_per_node > 0:
        return cput / 3600.0 * processors_per_node
    else:
        return cput


def report_metrics_to_accounting(audit, job_id, username, croupier_reporter_id, logger):
    workflow_id = ctx.workflow_id
    try:
        start_transaction = audit['start_timestamp']
        stop_transaction = audit['stop_timestamp']
        workflow_parameters = audit['workflow_parameters']

        if username is None:
            username = ctx.instance.runtime_properties['credentials']['user']
        try:
            user = accounting_client.get_user_by_name(username)
        except Exception:
            # User not registered
            try:
                user = User(username)
                user = accounting_client.add_user(user)
            except Exception as err:
                ctx.logger.error('User {0} could not be registered into Accounting, raising an error: {1}'
                                 .format(username, str(err)))
                raise Exception(
                    'User {0} could not be registered into Accounting, raising an error: {1}'
                        .format(username, str(err)))

        # Register HPC CPU total
        server = ctx.instance.runtime_properties['credentials']['host']
        infra = accounting_client.get_infrastructure_by_server(server)
        if infra is None:
            ctx.logger.error('Infrastructure not registered in Accounting for server {}'.format(server))
            raise Exception('Infrastructure not registered in Accounting for server {}'.format(server))
        cpu_resources = accounting_client.get_resources_by_type(infra.provider_id, infra.id, ResourceType.CPU)
        # Note: there should be ony one cpu_resource registered for target HPC infrastructure
        if len(cpu_resources) == 0:
            ctx.logger.error('CPU resource not registered in Accounting for server {}'.format(server))
            raise Exception('CPU resource not registered in Accounting for server {}'.format(server))
        cpu_resource = cpu_resources[0]

        consumptions = []
        cpu_consumption = ResourceConsumption(audit["cput"], MeasureUnit.Hours, cpu_resource.id)
        consumptions.append(cpu_consumption)

        record = ResourceConsumptionRecord(start_transaction, stop_transaction, workflow_id,
                                           job_id, workflow_parameters, consumptions, user.id, croupier_reporter_id)
        new_record = accounting_client.add_consumption_record(record)
        logger.info("Resource consumption record registered into Accounting with id {}".format(new_record.id))
    except Exception as err:
        logger.error(
            'Consumed resources by workflow {workflow_id} could not be reported to Accounting, raising an error: {err}'.
                format(workflow_id=workflow_id, err=str(err)))


def read_processors_per_node(job_id, workdir, ssh_client, logger):
    # Invoke command cat atosf9affs.audit
    command = 'cat {workdir}/{job_id}.audit'.format(job_id=job_id, workdir=workdir)
    output, exit_code = ssh_client.execute_shell_command(
        command,
        workdir=workdir,
        wait_result=True)
    if exit_code != 0:
        logger.warning('read_job_output: {command} failed with code: {code}:\n{output}'.format(
            command=command, code=str(exit_code), output=output))
        return 0
    else:
        return int(output[output.find('=') + 1:].rstrip("\n"))


def str_to_bool(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        raise ValueError
