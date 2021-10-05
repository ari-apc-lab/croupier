'''
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
'''
from __future__ import print_function
import os
import sys
import bottle
import configparser
from future import standard_library
from builtins import str
import socket
import traceback
from time import sleep, time
from datetime import datetime
import pytz

import requests
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from croupier_plugin.ssh import SshClient
from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (InfrastructureInterface)
from croupier_plugin.external_repositories.external_repository import (ExternalRepository)
from croupier_plugin.data_mover.datamover_proxy import (DataMoverProxy)
import croupier_plugin.vault.vault as vault
from croupier_plugin.accounting_client.model.user import (User)
from croupier_plugin.accounting_client.accounting_client import (AccountingClient)
from croupier_plugin.accounting_client.model.resource_consumption_record import (ResourceConsumptionRecord)
from croupier_plugin.accounting_client.model.resource_consumption import (ResourceConsumption, MeasureUnit)
from croupier_plugin.accounting_client.model.reporter import (Reporter, ReporterType)
from croupier_plugin.accounting_client.model.resource import (ResourceType)

standard_library.install_aliases()

accounting_client = AccountingClient()


@operation()
def download_vault_credentials(token, user, address, **kwargs):
    if not 'address':
        config = configparser.RawConfigParser()
        config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/Croupier.cfg'
        config.read(config_file)
        try:
            address = config.get('Vault', 'vault_address')
            if address is None:
                raise NonRecoverableError('Could not find Vault address in the croupier config file.')

        except configparser.NoSectionError:
            raise NonRecoverableError('Could not find the Vault section in the croupier config file.')

    address = address if address.startswith('http') else 'http://' + address

    if 'ssh_config' in ctx.source.instance.runtime_properties:
        ssh_config = ctx.source.instance.runtime_properties['ssh_config']
        ssh_config = vault.download_ssh_credentials(ssh_config, token, user, address)
        ctx.source.instance.runtime_properties['ssh_config'] = ssh_config

    if 'keycloak_credentials' in ctx.source.instance.runtime_properties:
        keycloak_credentials = ctx.source.instance.runtime_properties['keycloak_credentials']
        keycloak_credentials = vault.download_keycloak_credentials(keycloak_credentials, token, user, address)
        ctx.source.instance.runtime_properties['keycloak_credentials'] = keycloak_credentials


@operation
def preconfigure_interface(
        ssh_config,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Get interface config from infrastructure """
    ctx.logger.info('Preconfiguring infrastructure interface..')

    if not simulate:
        credentials_modified = False

        if 'ip' in ctx.target.instance.runtime_properties:
            ssh_config['host'] = \
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
                        ssh_config['private_key'] = private_key
                        credentials_modified = True
            elif node.type == 'cloudify.openstack.nodes.FloatingIP':
                # take public ip from openstack
                if 'floating_ip_address' in instance.runtime_properties:
                    ssh_config['host'] = \
                        instance.runtime_properties['floating_ip_address']
                    credentials_modified = True

        if credentials_modified:
            ctx.source.instance.runtime_properties['ssh_config'] = \
                ssh_config

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
        ssh_config,
        base_dir,
        workdir_prefix,
        monitoring_options,
        accounting_options,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Creates the working directory for the execution """
    ctx.logger.info('Connecting to infrastructure interface..')

    if not simulate:
        if 'infrastructure_interface' not in config:
            raise NonRecoverableError(
                "'infrastructure_interface' key missing on config")
        interface_type = config['infrastructure_interface']
        ctx.logger.info(' - manager: {interface_type}'.format(
            interface_type=interface_type))

        wm = InfrastructureInterface.factory(interface_type)
        if not wm:
            raise NonRecoverableError(
                "Infrastructure Interface '" +
                interface_type +
                "' not supported.")

        if 'ssh_config' in ctx.instance.runtime_properties:
            ssh_config = ctx.instance.runtime_properties['ssh_config']
        try:
            client = SshClient(ssh_config)
        except Exception as exp:
            raise NonRecoverableError(
                "Failed trying to connect to infrastructure interface: " + str(exp))

        # TODO: use command according to wm
        _, exit_code = client.execute_shell_command(
            'uname',
            wait_result=True)

        if exit_code != 0:
            client.close_connection()
            raise NonRecoverableError(
                "Failed executing on the infrastructure: exit code " +
                str(exit_code))

        ctx.instance.runtime_properties['login'] = exit_code == 0

        prefix = workdir_prefix if workdir_prefix else ctx.blueprint.name

        workdir = wm.create_new_workdir(client, base_dir, prefix, ctx.logger)
        client.close_connection()
        if workdir is None:
            raise NonRecoverableError(
                "failed to create the working directory, base dir: " +
                base_dir)
        ctx.instance.runtime_properties['workdir'] = workdir

        # Register Croupier instance in Accounting if not done before
        if accounting_client.report_to_accounting:
            registerOrchestratorInstanceInAccounting(ctx)

        # Registering accounting and monitoring options
        ctx.instance.runtime_properties['monitoring_options'] = monitoring_options
        ctx.instance.runtime_properties['accounting_options'] = accounting_options
        ctx.instance.runtime_properties['infrastructure_host'] = ssh_config['host']

        ctx.logger.info('..infrastructure ready to be used on ' + workdir)
    else:
        ctx.logger.info(' - [simulation]..')
        ctx.instance.runtime_properties['login'] = True
        ctx.instance.runtime_properties['workdir'] = "simulation"
        ctx.logger.warning('Infrastructure Interface connection simulated')


@operation
def cleanup_execution(
        config,
        ssh_config,
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
        wm = InfrastructureInterface.factory(interface_type)
        if not wm:
            raise NonRecoverableError(
                "Infrastructure Interface '" +
                interface_type +
                "' not supported.")

        if 'ssh_config' in ctx.instance.runtime_properties:
            ssh_config = ctx.instance.runtime_properties['ssh_config']
        client = SshClient(ssh_config)
        client.execute_shell_command(
            'rm -r ' + workdir,
            wait_result=True)
        client.close_connection()

        ctx.logger.info('..all clean.')
    else:
        ctx.logger.warning('clean up simulated.')

@operation
def configure_monitor(address, **kwargs):
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
        monitoring_id = ctx.deployment.name + ctx.deployment.id
        ctx.logger.info("Monitoring_id generated: " + monitoring_id)
        ctx.instance.runtime_properties["monitoring_id"] = monitoring_id

        ctx.instance.runtime_properties["hpc_exporter_address"] = address if address.startswith("http") \
            else "http://" + address


@operation
def preconfigure_interface_monitor(**kwargs):
    ctx.source.instance.runtime_properties["monitoring_id"] = \
        ctx.target.instance.runtime_properties["monitoring_id"]
    ctx.source.instance.runtime_properties["hpc_exporter_address"] = \
        ctx.target.instance.runtime_properties["hpc_exporter_address"]


@operation
def start_monitoring_hpc(
        config_infra,
        ssh_config,
        monitoring_options,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Starts monitoring using the HPC Exporter """

    if not simulate and "hpc_exporter_address" in ctx.instance.runtime_properties and \
            ctx.instance.runtime_properties["hpc_exporter_address"]:
        monitoring_id = ctx.instance.runtime_properties["monitoring_id"]
        hpc_exporter_address = ctx.instance.runtime_properties["hpc_exporter_address"]
        ctx.logger.info('Creating Collector in HPC Exporter...')
        if 'ssh_config' in ctx.instance.runtime_properties:
            ssh_config = ctx.instance.runtime_properties['ssh_config']
        infrastructure_interface = config_infra['infrastructure_interface'].lower()
        infrastructure_interface = "pbs" if infrastructure_interface is "torque" else infrastructure_interface
        monitor_period = monitoring_options["monitor_period"] if "monitor_period" in monitoring_options else 30

        deployment_label = monitoring_options["deployment_label"] if "deployment_label" in monitoring_options\
            else ctx.deployment.id
        hpc_label = monitoring_options["hpc_label"] if "hpc_label" in monitoring_options else ctx.node.name
        only_jobs = monitoring_options["only_jobs"] if "only_jobs" in monitoring_options else False

        if (infrastructure_interface != "slurm") and (infrastructure_interface != "pbs"):
            ctx.logger.warning("HPC Exporter doesn't support '{0}' interface. Collector will not be created."
                               .format(infrastructure_interface))
            ctx.instance.runtime_properties["hpc_exporter_address"] = None
            return

        payload = {
            "host": ssh_config["host"],
            "scheduler": infrastructure_interface,
            "scrape_interval": monitor_period,
            "deployment_label": deployment_label,
            "monitoring_id": monitoring_id,
            "hpc_label": hpc_label,
            "only_jobs": only_jobs,
            "ssh_user": ssh_config["user"]
        }

        if "password" in ssh_config and ssh_config["password"]:
            payload["ssh_password"] = ssh_config["password"]
        else:
            payload["ssh_pkey"] = ssh_config["private_key"]

        url = hpc_exporter_address + '/collector'
        ctx.logger.info("Creating collector in " + str(url))
        response = requests.request("POST", url, json=payload)

        if not response.ok:
            ctx.logger.error("Failed to start node monitor: {0}: {1}".format(response.status_code, response.content))
            return
        ctx.logger.info("Monitor started for HPC: {0} ({1})".format(ssh_config["host"], hpc_label))
    elif simulate:
        ctx.logger.warning('monitor simulated')
    else:
        ctx.logger.warning("No HPC Exporter selected for node {0}. Won't create a collector in any HPC Exporter for it."
                           .format(ctx.node.name))


@operation
def stop_monitoring_hpc(
        ssh_config,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Removes the HPC Exporter's collector """

    if "hpc_exporter_address" in ctx.instance.runtime_properties and \
            ctx.instance.runtime_properties["hpc_exporter_address"]:
        hpc_exporter_address = ctx.instance.runtime_properties["hpc_exporter_address"]
        ctx.logger.info('Removing collector from HPC Exporter...')

        if not simulate:
            host = ssh_config['host']
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
def preconfigure_job(
        config,
        ssh_config,
        job_prefix,
        monitoring_options,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Match the job with its ssh_config """
    ctx.logger.info('Preconfiguring job..')

    if 'ssh_config' not in ctx.target.instance.runtime_properties:
        ctx.source.instance.runtime_properties['ssh_config'] = ssh_config
    else:
        ctx.source.instance.runtime_properties['ssh_config'] = ctx.target.instance.runtime_properties['ssh_config']
    ctx.source.instance.runtime_properties['monitoring_options'] = monitoring_options
    ctx.source.instance.runtime_properties['infrastructure_interface'] = config['infrastructure_interface']
    ctx.source.instance.runtime_properties['reservation_deletion_path'] = config['reservation_deletion_path']
    ctx.source.instance.runtime_properties['timezone'] = config['country_tz']
    ctx.source.instance.runtime_properties['simulate'] = simulate
    ctx.source.instance.runtime_properties['job_prefix'] = job_prefix
    ctx.source.instance.runtime_properties['workdir'] = ctx.target.instance.runtime_properties['workdir']
    if 'hpc_exporter_address' in ctx.target.instance.runtime_properties and \
            ctx.target.instance.runtime_properties['hpc_exporter_address']:
        ctx.source.instance.runtime_properties['hpc_exporter_address'] = \
            ctx.target.instance.runtime_properties['hpc_exporter_address']
        ctx.source.instance.runtime_properties['monitoring_id'] = \
            ctx.target.instance.runtime_properties['monitoring_id']


@operation
def bootstrap_job(
        deployment,
        skip_cleanup,
        **kwargs):  # pylint: disable=W0613
    """Bootstrap a job with a script that receives SSH credentials as input"""
    if not deployment:
        return

    ctx.logger.info('Bootstraping job..')
    simulate = ctx.instance.runtime_properties['simulate']

    if not simulate and 'bootstrap' in deployment and deployment['bootstrap']:
        inputs = deployment['inputs'] if 'inputs' in deployment else []
        ssh_config = ctx.instance.runtime_properties['ssh_config']
        workdir = ctx.instance.runtime_properties['workdir']
        name = "bootstrap_" + ctx.instance.id + ".sh"
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']

        if deploy_job(
                deployment['bootstrap'],
                inputs,
                ssh_config,
                interface_type,
                workdir,
                name,
                ctx.logger,
                skip_cleanup):
            ctx.logger.info('..job bootstraped')
        else:
            ctx.logger.error('Job not bootstraped')
            raise NonRecoverableError("Bootstrap failed")
    else:
        if 'bootstrap' in deployment and deployment['bootstrap']:
            ctx.logger.warning('..bootstrap simulated')
        else:
            ctx.logger.info('..nothing to bootstrap')


@operation
def revert_job(deployment, skip_cleanup, **kwarsgs):  # pylint: disable=W0613
    """Revert a job using a script that receives SSH ssh_config as input"""
    if not deployment:
        return

    ctx.logger.info('Reverting job..')
    try:
        simulate = ctx.instance.runtime_properties['simulate']

        if not simulate and 'revert' in deployment and deployment["revert"]:
            inputs = deployment['inputs'] if 'inputs' in deployment else []
            ssh_config = ctx.instance.runtime_properties['ssh_config']
            workdir = ctx.instance.runtime_properties['workdir']
            name = "revert_" + ctx.instance.id + ".sh"
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']

            if deploy_job(
                    deployment['revert'],
                    inputs,
                    ssh_config,
                    interface_type,
                    workdir,
                    name,
                    ctx.logger,
                    skip_cleanup):
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
        ctx.logger.warning('Job was not reverted as it was not configured')


def deploy_job(script,
               inputs,
               ssh_config,
               interface_type,
               workdir,
               name,
               logger,
               skip_cleanup):  # pylint: disable=W0613
    """ Exec a deployment job script that receives SSH ssh_config as input """

    wm = InfrastructureInterface.factory(interface_type)
    if not wm:
        raise NonRecoverableError(
            "Infrastructure Interface '" +
            interface_type +
            "' not supported.")

    # Execute the script and manage the output
    success = False
    client = SshClient(ssh_config)
    script_content = script if script[0] == '#' else ctx.get_resource(script)
    if wm.create_shell_script(client,
                              name,
                              script_content,
                              logger,
                              workdir=workdir):
        call = "./" + name
        for dinput in inputs:
            str_input = str(dinput)
            if ('\n' in str_input or ' ' in str_input) and str_input[0] != '"':
                call += ' "' + str_input + '"'
            else:
                call += ' ' + str_input
        _, exit_code = client.execute_shell_command(
            call,
            workdir=workdir,
            wait_result=True)
        if exit_code != 0:
            logger.warning("failed to deploy job: call '" + call + "', exit code " + str(exit_code))
        else:
            success = True

        if not skip_cleanup:
            if not client.execute_shell_command("rm " + name, workdir=workdir):
                logger.warning("failed removing bootstrap script")

    client.close_connection()

    return success


@operation
def send_job(job_options, data_mover_options, **kwargs):  # pylint: disable=W0613
    """ Sends a job to the infrastructure interface """
    ctx.logger.info('Executing send_job task')
    simulate = ctx.instance.runtime_properties['simulate']

    name = kwargs['name']
    is_singularity = 'croupier.nodes.SingularityJob' in ctx.node.type_hierarchy

    if 'reservation' in job_options and 'recurrent_reservation' in job_options and job_options['recurrent_reservation']:
        reservation_id = job_options['reservation']
        if 'recurrent_reservation' in job_options and job_options['recurrent_reservation']:
            timezone = ctx.instance.runtime_properties['timezone']
            job_options['reservation'] = datetime.now(tz=pytz.timezone(timezone)).strftime(reservation_id)
        ctx.instance.runtime_properties['reservation'] = reservation_id

    if not simulate:
        # Do data download (from Cloud to HPC) if requested
        if len(data_mover_options) > 0 and \
                'download' in data_mover_options and data_mover_options['download']:
            if 'hpc_target' in data_mover_options and 'cloud_target' in data_mover_options:
                try:
                    dmp = DataMoverProxy(data_mover_options, ctx.logger)
                    source = data_mover_options['cloud_target']
                    destination = data_mover_options['hpc_target']
                    source_input = data_mover_options['download']['source']
                    dest_output = data_mover_options['download']['target']
                    dmp.move_data(source, destination, source_input, dest_output)
                except Exception as exp:
                    ctx.logger.error("Error using data mover: {}".format(str(exp)))

        # Prepare HPC interface to send job
        workdir = ctx.instance.runtime_properties['workdir']
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        client = SshClient(ctx.instance.runtime_properties['ssh_config'])

        wm = InfrastructureInterface.factory(interface_type)
        if not wm:
            client.close_connection()
            raise NonRecoverableError(
                "Infrastructure Interface '" +
                interface_type +
                "' not supported.")
        context_vars = {
            'CFY_EXECUTION_ID': ctx.execution_id,
            'CFY_JOB_NAME': name
        }
        ctx.logger.info('Submitting the job ...')

        try:
            jobid = wm.submit_job(
                client,
                name,
                job_options,
                is_singularity,
                ctx.logger,
                workdir=workdir,
                context=context_vars)
        except Exception as ex:
            ctx.logger.error('Job could not be submitted because error ' + str(ex))
            raise ex
        client.close_connection()
    else:
        ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')
        is_submitted = True
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
                    ctx.instance.runtime_properties['ssh_config']['host'])
    ctx.instance.update()


@operation
def delete_reservation():
    if not ('reservation' in ctx.instance.runtime_properties) and not\
            ('reservation_deletion_path' in ctx.instance.runtime_properties):
        return
    reservation_id = ctx.instance.runtime_properties['reservation']
    interface_type = ctx.instance.runtime_properties['infrastructure_interface']
    client = SshClient(ctx.instance.runtime_properties['ssh_config'])
    deletion_path = ctx.instance.runtime_properties['reservation_deletion_path']
    wm = InfrastructureInterface.factory(interface_type)
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
        ctx.logger.error('Reservation could not be deleted because: ' + ex.message)
        raise ex
    client.close_connection()

    if ok:
        ctx.logger.info('Reservation with ID {0} deleted successfully'.format(reservation_id))
    else:
        ctx.logger.warning('Reservation with ID {0} could not be deleted, it might have been already been deleted'
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
        ctx.logger.error('Job was not cleaned up as it was not configured')
        return

    try:
        name = kwargs['name']
        if not simulate:
            is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
                type_hierarchy
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['ssh_config'])

            wm = InfrastructureInterface.factory(interface_type)
            if not wm:
                client.close_connection()
                raise NonRecoverableError("Infrastructure Interface '" + interface_type + "' not supported.")
            is_clean = wm.clean_job_aux_files(client,
                                              name,
                                              job_options,
                                              is_singularity,
                                              ctx.logger,
                                              workdir=workdir)

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
            'Something happened when trying to clean up:' + '\n' + traceback.format_exc() + '\n' + str(exp))


@operation
def stop_job(job_options, **kwargs):  # pylint: disable=W0613
    """ Stops a job in the infrastructure """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, no need to be stopped
        ctx.logger.error('Job was not stopped as it was not configured properly.')
        return

    try:
        name = kwargs['name']
        is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
            type_hierarchy

        if not simulate:
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['ssh_config'])

            wm = InfrastructureInterface.factory(interface_type)
            if not wm:
                client.close_connection()
                raise NonRecoverableError(
                    "Infrastructure Interface '" +
                    interface_type +
                    "' not supported.")
            is_stopped = wm.stop_job(client,
                                     name,
                                     job_options,
                                     is_singularity,
                                     ctx.logger,
                                     workdir=workdir)

            client.close_connection()
        else:
            ctx.logger.warning('Instance ' + ctx.instance.id + ' simulated')
            is_stopped = True

        if is_stopped:
            ctx.logger.info(
                'Job ' + name + ' (' + ctx.instance.id + ') stopped.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id +
                             ') not stopped.')
            raise NonRecoverableError('Job ' + name + ' (' + ctx.instance.id +
                                      ') not stopped.')
    except Exception as exp:
        ctx.logger.error('Something happened when trying to stop:' + '\n' + traceback.format_exc() + '\n' + str(exp))


@operation
def publish(publish_list, data_mover_options, **kwargs):
    """ Publish the job outputs """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, no need to publish
        ctx.logger.warning('Job outputs where not published as the job was not configured properly.')
        return

    try:
        name = kwargs['name']
        audit = kwargs['audit']
        published = True
        if not simulate:
            # Do data upload (from HPC to Cloud) if requested
            if len(data_mover_options) > 0 and \
                    'upload' in data_mover_options and data_mover_options['upload']:
                if 'hpc_target' in data_mover_options and 'cloud_target' in data_mover_options:
                    try:
                        dmp = DataMoverProxy(data_mover_options, ctx.logger)
                        source = data_mover_options['hpc_target']
                        destination = data_mover_options['cloud_target']
                        source_input = data_mover_options['upload']['source']
                        dest_output = data_mover_options['upload']['target']
                        dmp.move_data(source, destination, source_input, dest_output)
                    except Exception as exp:
                        ctx.logger.error('Error using data mover: {}:\n' + traceback.format_exc() + '\n' + str(exp))

            workdir = ctx.instance.runtime_properties['workdir']
            client = SshClient(ctx.instance.runtime_properties['ssh_config'])

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
def ecmwf_vertical_interpolation(query, **kwargs):
    ALGORITHMS = ["sequential", "semi_parallel", "fully_parallel"]
    server_port = ctx.node.properties['port']
    server_host = requests.get('https://api.ipify.org').text
    keycloak_credentials = ctx.instance.runtime_properties["keycloak_credentials"]
    ecmwf_ssh_credentials = ctx.instance.runtime_properties["ssh_config"]
    ctx.logger.info('IP is: ' + server_host)

    arguments = {"notify": "http://" + server_host + ":" + str(server_port) + "/ready",
                 "user_name": keycloak_credentials["user"],
                 "password": keycloak_credentials["pw"],
                 "params": query["params"],
                 "area": query["area"],
                 "max_step": query["max_step"],
                 "ensemble": query["ensemble"],
                 "input": query["input"] ,
                 "members": query["members"],
                 "keep_input": query["keep_input"],
                 "collection": query["collection"],
                 "algorithm": query["algorithm"] if "algorithm" in query and query[
                     "algorithm"] in ALGORITHMS else ""}

    if query["date"]:
        arguments["date"] = query["date"]
        arguments["time"] = query["time"]

    client = SshClient(ecmwf_ssh_credentials)

    command = "cd cloudify && source /opt/anaconda3/etc/profile.d/conda.sh && conda activate && " \
              "nohup python3 interpolator.py"

    for arg in arguments:
        command += " --" + arg + " " + str(arguments[arg]) if arguments[arg] is not "" else ""

    # out_file = str(time())
    out_file = "/dev/null"
    command += " > " + out_file + " 2>&1 & disown"

    ctx.logger.info("Sending command: " + command)
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
                ctx.instance.runtime_properties['data_urls'] = [data["file"]]
                ctx.logger.info("Process completed, stdout:\n" + data["stdout"])
                ctx.logger.info("CKAN URL: " + ctx.instance.runtime_properties['ckan_url'])
                return 200
            else:
                ctx.logger.error(data)
                ctx.logger.error("Non valid response from ECMWF received")
        finally:
            sys.stderr.close()

    try:
        ctx.logger.info("Listening in: " + server_host + ":" + str(server_port))
        bottle.run(host='0.0.0.0', port=server_port)
    except ValueError:
        pass


@operation
def download_data(**kwargs):
    ctx.logger.info('Downloading data...')
    simulate = ctx.instance.runtime_properties['simulate']

    if not simulate and 'data_urls' in ctx.instance.runtime_properties \
            and ctx.instance.runtime_properties['data_urls']:
        data_urls = ctx.instance.runtime_properties['data_urls']
        inputs = data_urls
        credentials = ctx.instance.runtime_properties['credentials']
        workdir = ctx.node.properties["dest_data"] if ctx.node.properties["dest_data"] \
            else ctx.instance.runtime_properties['workdir']
        name = "data_download_" + ctx.instance.id + ".sh"
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        script = data_download_unzip_script() if 'unzip_data' in ctx.node.properties and ctx.node.properties[
            'unzip_data'] \
            else data_download_script()
        skip_cleanup = False
        if deploy_job(script, inputs, credentials, interface_type, workdir, name, ctx.logger, skip_cleanup):
            ctx.logger.info('...data downloaded')
            files_downloaded = ctx.instance.runtime_properties['files_downloaded'] \
                if 'files_downloaded' in ctx.instance.runtime_properties else []
            if 'unzip_data' in ctx.node.properties and ctx.node.properties['unzip_data']:
                # TODO: save filenames after being unzipped so they can be deleted
                pass
            else:
                for url in data_urls:
                    files_downloaded.append(url.rpartition('/')[-1])

            ctx.instance.runtime_properties['files_downloaded'] = files_downloaded
        else:
            ctx.logger.error('Data could not be downloaded')
            raise NonRecoverableError("Data failed to download")
    elif 'data_urls' in ctx.instance.runtime_properties and ctx.instance.runtime_properties['data_urls']:
        ctx.logger.info("... data download simulated")
    else:
        ctx.logger.warning('...nothing to download')
        raise NonRecoverableError("There was no data to download")


@operation
def delete_data(**kwargs):
    simulate = ctx.instance.runtime_properties['simulate']
    if "files_downloaded" in ctx.instance.runtime_properties and ctx.instance.runtime_properties['files_downloaded'] \
            and not simulate:
        inputs = ctx.instance.runtime_properties["files_downloaded"]
        credentials = ctx.instance.runtime_properties['credentials']
        workdir = ctx.node.properties["dest_data"] if ctx.node.properties["dest_data"] \
            else ctx.instance.runtime_properties['workdir']
        name = "data_download_" + ctx.instance.id + ".sh"
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        script = data_delete_script()
        skip_cleanup = False
        if deploy_job(script, inputs, credentials, interface_type, workdir, name, ctx.logger, skip_cleanup):
            ctx.logger.info('...data deleted')
            ctx.instance.runtime_properties["files_downloaded"] = []
        else:
            ctx.logger.error('Data could not be deleted')
    elif 'files_downloaded' in ctx.instance.runtime_properties and ctx.instance.runtime_properties['files_downloaded']:
        ctx.logger.info("...data deletion simulated")
    else:
        ctx.logger.warning('...nothing to delete')


@operation
def preconfigure_data(
        config,
        credentials,
        external_monitor_entrypoint,
        external_monitor_port,
        external_monitor_type,
        external_monitor_orchestrator_port,
        monitor_period,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Save infrastructure properties in the data node instance (credentials, etc.) """
    ctx.logger.info('Preconfiguring data..')

    if 'credentials' not in ctx.target.instance.runtime_properties:
        ctx.source.instance.runtime_properties['credentials'] = credentials
    else:
        ctx.source.instance.runtime_properties['credentials'] = ctx.target.instance.runtime_properties['credentials']

    ctx.source.instance.runtime_properties['external_monitor_entrypoint'] = external_monitor_entrypoint
    ctx.source.instance.runtime_properties['external_monitor_port'] = external_monitor_port
    ctx.source.instance.runtime_properties['external_monitor_type'] = external_monitor_type
    ctx.source.instance.runtime_properties['monitor_orchestrator_port'] = external_monitor_orchestrator_port
    ctx.source.instance.runtime_properties['infrastructure_interface'] = config['infrastructure_interface']
    ctx.source.instance.runtime_properties['simulate'] = simulate
    ctx.source.instance.runtime_properties['monitor_period'] = monitor_period
    ctx.source.instance.runtime_properties['workdir'] = ctx.target.instance.runtime_properties['workdir']


@operation
def pass_data_info(**kwargs):
    files_downloaded = ctx.source.instance.runtime_properties['files_downloaded'] if \
        'files_downloaded' in ctx.source.instance.runtime_properties else []
    if 'files_downloaded' in ctx.target.instance.runtime_properties:
        for file in ctx.target.instance.runtime_properties['files_downloaded']:
            files_downloaded.append(file)
    ctx.source.instance.runtime_properties['files_downloaded'] = files_downloaded


def getHours(cput):
    return int(cput[:cput.index(':')])


def getMinutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def getSeconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def parseHours(cput):
    hours = getHours(cput) + getMinutes(cput) / 60.0 + getSeconds(cput) / 3600.0
    return hours


def monitor_job(jobid, hpc_exporter_entrypoint, deployment_id, host):
    url = hpc_exporter_entrypoint + "/job"
    payload = {
        "monitoring_id": deployment_id,
        "host": host,
        "job_id": jobid
    }
    requests.post(url, json=payload)


def registerOrchestratorInstanceInAccounting(ctx):
    hostname = socket.gethostname()
    reporter_name = 'croupier@' + hostname

    try:
        reporter = accounting_client.get_reporter_by_name(reporter_name)
        ctx.instance.runtime_properties['croupier_reporter_id'] = reporter.id
        ctx.logger.info('Registered Croupier reporter in Accounting with id {}'.format(reporter.id))
    except Exception as err:
        # Croupier not registered in Accounting
        try:
            ip = requests.get('https://api.ipify.org').text
            reporter = Reporter(reporter_name, ip, ReporterType.Orchestrator)
            reporter = accounting_client.add_reporter(reporter)
            ctx.instance.runtime_properties['croupier_reporter_id'] = reporter.id
        except Exception as err:
            ctx.logger.warning(
                'Croupier orchestrator instance could not be registered into Accounting, raising an error: {err}'.
                    format(err=err))



def convert_cput(cput, job_id, workdir, ssh_client, logger):
    processors_per_node = read_processors_per_node(job_id, workdir, ssh_client, logger)
    if processors_per_node > 0:
        return cput / 3600.0 * processors_per_node
    else:
        return cput


def report_metrics_to_accounting(audit, job_id, username, croupier_reporter_id, logger):
    try:
        workflow_id = ctx.workflow_id
        start_transaction = audit['start_timestamp']
        stop_transaction = audit['stop_timestamp']
        workflow_parameters = audit['workflow_parameters']

        if username is None:
            username = ctx.instance.runtime_properties['ssh_config']['user']
        try:
            user = accounting_client.get_user_by_name(username)
        except Exception as err:
            # User not registered
            try:
                user = User(username)
                user = accounting_client.add_user(user)
            except Exception as err:
                raise Exception(
                    'User {username} could not be registered into Accounting, raising an error: {err}'.
                        format(username=username, err=err))

        # Register HPC CPU total
        server = ctx.instance.runtime_properties['ssh_config']['host']
        infra = accounting_client.get_infrastructure_by_server(server)
        if infra is None:
            raise Exception('Infrastructure not registered in Accounting for server {}'.format(server))
        cpu_resources = accounting_client.get_resources_by_type(infra.provider_id, infra.id, ResourceType.CPU)
        # Note: there should be ony one cpu_resource registered for target HPC infrastructure
        if len(cpu_resources) == 0:
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
                format(workflow_id=workflow_id, err=err))


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


def data_download_script():
    return '#!/bin/bash\nfor url in "$@"\ndo\n  wget "$url"\ndone'


def data_download_unzip_script():
    return '#!/usr/bin/env bash\nfor url in "$@"\ndo\n  wget "$url"\n  filename=$(basename "$url")\n  unzip ' \
           '"$filename"\n  rm "$filename"\ndone '


def data_delete_script():
    return '#!/bin/bash\nfor file in "$@"\ndo\n  rm -r "$file"\ndone'


def str_to_bool(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        raise ValueError