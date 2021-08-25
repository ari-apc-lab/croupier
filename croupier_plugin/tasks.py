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
from future import standard_library
standard_library.install_aliases()
from builtins import str
import socket
import traceback
from time import sleep
import threading

import requests
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from croupier_plugin.monitoring.monitoring import (PrometheusPublisher)
from croupier_plugin.workflows import JobGraphInstance
from croupier_plugin.ssh import SshClient
from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (InfrastructureInterface)
from croupier_plugin.external_repositories.external_repository import (ExternalRepository)
from croupier_plugin.data_mover.datamover_proxy import (DataMoverProxy)
from croupier_plugin.accounting_client.model.user import (User)
from croupier_plugin.accounting_client.accounting_client import (AccountingClient)
from croupier_plugin.accounting_client.model.resource_consumption_record import (ResourceConsumptionRecord)
from croupier_plugin.accounting_client.model.resource_consumption import (ResourceConsumption, MeasureUnit)
from croupier_plugin.accounting_client.model.reporter import (Reporter, ReporterType)
from croupier_plugin.accounting_client.model.resource import (ResourceType)

# from celery.contrib import rdb

accounting_client = AccountingClient()
monitoring_client = PrometheusPublisher()

# Keep track of forked thread for monitoring reporting
forkedThreads = list()


def addThread(thread):
    global forkedThreads
    forkedThreads.append(thread)


def joinThreads():
    global forkedThreads
    for thread in forkedThreads:
        thread.join
    forkedThreads = []


@operation
def preconfigure_interface(
        config,
        credentials,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Get interface config from infrastructure """
    ctx.logger.info('Preconfiguring infrastructure interface..')

    if not simulate:
        credentials_modified = False

        if 'ip' in ctx.target.instance.runtime_properties:
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

        if 'credentials' in ctx.instance.runtime_properties:
            credentials = ctx.instance.runtime_properties['credentials']
        try:
            client = SshClient(credentials)
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

        prefix = workdir_prefix
        if workdir_prefix == "":
            prefix = ctx.blueprint.id

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
        ctx.instance.runtime_properties['infrastructure_host'] = credentials['host']

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

    # Wait for all forked threads to complete
    joinThreads()

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
def start_monitoring_hpc(
        config,
        credentials,
        external_monitor_entrypoint,
        external_monitor_port,
        external_monitor_orchestrator_port,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Starts monitoring using the Monitor orchestrator """
    external_monitor_entrypoint = None  # FIXME: external monitor disabled
    if external_monitor_entrypoint:
        ctx.logger.info('Starting infrastructure monitor..')

        if not simulate:
            if 'credentials' in ctx.instance.runtime_properties:
                credentials = ctx.instance.runtime_properties['credentials']
            infrastructure_interface = config['infrastructure_interface']
            country_tz = config['country_tz']

            url = 'http://' + external_monitor_entrypoint + \
                  external_monitor_orchestrator_port + '/exporters/add'

            # FIXME: credentials doesn't have to have a password anymore
            payload = ("{\n\t\"host\": \"" + credentials['host'] +
                       "\",\n\t\"type\": \"" + infrastructure_interface +
                       "\",\n\t\"persistent\": false,\n\t\"args\": {\n\t\t\""
                       "user\": \"" + credentials['user'] + "\",\n\t\t\""
                       "pass\": \"" + credentials['password'] + "\",\n\t\t\""
                       "tz\": \"" + country_tz + "\",\n\t\t\""
                       "log\": \"debug\"\n\t}\n}")
            headers = {
                'content-type': "application/json",
                'cache-control': "no-cache",
            }

            response = requests.request(
                "POST", url, data=payload, headers=headers)

            if response.status_code != 201:
                raise NonRecoverableError("failed to start node monitor: " + str(response.status_code))
        else:
            ctx.logger.warning('monitor simulated')


@operation
def stop_monitoring_hpc(
        config,
        credentials,
        external_monitor_entrypoint,
        external_monitor_port,
        external_monitor_orchestrator_port,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Stops monitoring using the Monitor Orchestrator """
    external_monitor_entrypoint = None  # FIXME: external monitor disabled
    if external_monitor_entrypoint:
        ctx.logger.info('Stoping infrastructure monitor..')

        if not simulate:
            if 'credentials' in ctx.instance.runtime_properties:
                credentials = ctx.instance.runtime_properties['credentials']
            infrastructure_interface = config['infrastructure_interface']
            country_tz = config['country_tz']

            url = 'http://' + external_monitor_entrypoint + \
                  external_monitor_orchestrator_port + '/exporters/remove'

            # FIXME: credentials doesn't have to have a password anymore
            payload = ("{\n\t\"host\": \"" + credentials['host'] +
                       "\",\n\t\"type\": \"" + infrastructure_interface +
                       "\",\n\t\"persistent\": false,\n\t\"args\": {\n\t\t\""
                       "user\": \"" + credentials['user'] + "\",\n\t\t\""
                       "pass\": \"" + credentials['password'] + "\",\n\t\t\""
                       "tz\": \"" + country_tz + "\",\n\t\t\""
                       "log\": \"debug\"\n\t}\n}")
            headers = {
                'content-type': "application/json",
                'cache-control': "no-cache",
            }

            response = requests.request(
                "POST", url, data=payload, headers=headers)

            if response.status_code != 200:
                if response.status_code == 409:
                    ctx.logger.warning(
                        'Already removed on the exporter orchestrator.')
                else:
                    raise NonRecoverableError("failed to stop node monitor: " + str(response.status_code))
        else:
            ctx.logger.warning('monitor simulated')


@operation
def preconfigure_job(
        config,
        credentials,
        external_monitor_entrypoint,
        external_monitor_port,
        external_monitor_type,
        external_monitor_orchestrator_port,
        job_prefix,
        monitor_period,
        simulate,
        **kwargs):  # pylint: disable=W0613
    """ Match the job with its credentials """
    ctx.logger.info('Preconfiguring job..')

    if 'credentials' not in ctx.target.instance.runtime_properties:
        ctx.source.instance.runtime_properties['credentials'] = \
            credentials
    else:
        ctx.source.instance.runtime_properties['credentials'] = \
            ctx.target.instance.runtime_properties['credentials']

    ctx.source.instance.runtime_properties['external_monitor_entrypoint'] = \
        external_monitor_entrypoint
    ctx.source.instance.runtime_properties['external_monitor_port'] = \
        external_monitor_port
    ctx.source.instance.runtime_properties['external_monitor_type'] = \
        external_monitor_type
    ctx.source.instance.runtime_properties['monitor_orchestrator_port'] = \
        external_monitor_orchestrator_port
    ctx.source.instance.runtime_properties['infrastructure_interface'] = \
        config['infrastructure_interface']
    ctx.source.instance.runtime_properties['simulate'] = simulate
    ctx.source.instance.runtime_properties['job_prefix'] = job_prefix
    ctx.source.instance.runtime_properties['monitor_period'] = monitor_period

    ctx.source.instance.runtime_properties['workdir'] = \
        ctx.target.instance.runtime_properties['workdir']


@operation
def bootstrap_job(
        deployment,
        skip_cleanup,
        **kwarsgs):  # pylint: disable=W0613
    """Bootstrap a job with a script that receives SSH credentials as input"""
    if not deployment:
        return

    ctx.logger.info('Bootstraping job..')
    simulate = ctx.instance.runtime_properties['simulate']

    if not simulate and 'bootstrap' in deployment:
        inputs = deployment['inputs'] if 'inputs' in deployment else []
        credentials = ctx.instance.runtime_properties['credentials']
        workdir = ctx.instance.runtime_properties['workdir']
        name = "bootstrap_" + ctx.instance.id + ".sh"
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']

        if deploy_job(
                deployment['bootstrap'],
                inputs,
                credentials,
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
        if 'bootstrap' in deployment:
            ctx.logger.warning('..bootstrap simulated')
        else:
            ctx.logger.info('..nothing to bootstrap')


@operation
def revert_job(deployment, skip_cleanup, **kwarsgs):  # pylint: disable=W0613
    """Revert a job using a script that receives SSH credentials as input"""
    if not deployment:
        return

    ctx.logger.info('Reverting job..')
    try:
        simulate = ctx.instance.runtime_properties['simulate']

        if not simulate and 'revert' in deployment:
            inputs = deployment['inputs'] if 'inputs' in deployment else []
            credentials = ctx.instance.runtime_properties['credentials']
            workdir = ctx.instance.runtime_properties['workdir']
            name = "revert_" + ctx.instance.id + ".sh"
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']

            if deploy_job(
                    deployment['revert'],
                    inputs,
                    credentials,
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
            if 'revert' in deployment:
                ctx.logger.warning('..revert simulated')
            else:
                ctx.logger.info('..nothing to revert')
    except KeyError:
        # The job wasn't configured properly, so there was no bootstrap
        ctx.logger.warning('Job was not reverted as it was not configured')


def deploy_job(script,
               inputs,
               credentials,
               interface_type,
               workdir,
               name,
               logger,
               skip_cleanup):  # pylint: disable=W0613
    """ Exec a deployment job script that receives SSH credentials as input """

    wm = InfrastructureInterface.factory(interface_type)
    if not wm:
        raise NonRecoverableError(
            "Infrastructure Interface '" +
            interface_type +
            "' not supported.")

    # Execute the script and manage the output
    success = False
    client = SshClient(credentials)
    if wm._create_shell_script(client,
                               name,
                               ctx.get_resource(script),
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
            logger.warning(
                "failed to deploy job: call '" + call + "', exit code " +
                str(exit_code))
        else:
            success = True

        if not skip_cleanup:
            if not client.execute_shell_command(
                    "rm " + name,
                    workdir=workdir):
                logger.warning("failed removing bootstrap script")

    client.close_connection()

    return success


@operation
def send_job(job_options, data_mover_options, **kwargs):  # pylint: disable=W0613
    """ Sends a job to the infrastructure interface """
    ctx.logger.info('Executing send_job task')
    simulate = ctx.instance.runtime_properties['simulate']

    name = kwargs['name']
    is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
        type_hierarchy

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
                    ctx.logger.error("Error using data mover: {}".format(exp.message))

        # Prepare HPC interface to send job
        workdir = ctx.instance.runtime_properties['workdir']
        interface_type = ctx.instance.runtime_properties['infrastructure_interface']
        client = SshClient(ctx.instance.runtime_properties['credentials'])

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
            ctx.logger.error('Job could not be submitted because error ' + ex.message)
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
    ctx.instance.update()


@operation
def cleanup_job(job_options, skip, **kwargs):  # pylint: disable=W0613
    """Clean the aux files of the job"""
    if skip:
        return

    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, so no cleanup needed
        ctx.logger.warning('Job was not cleaned up as it was not configured.')

    try:
        name = kwargs['name']
        if not simulate:
            is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
                type_hierarchy
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

            wm = InfrastructureInterface.factory(interface_type)
            if not wm:
                client.close_connection()
                raise NonRecoverableError(
                    "Infrastructure Interface '" +
                    interface_type +
                    "' not supported.")
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
            ctx.logger.info(
                'Job ' + name + ' (' + ctx.instance.id + ') cleaned.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id + ') not cleaned.')
    except Exception as exp:
        print(traceback.format_exc())
        ctx.logger.error(
            'Something happend when trying to clean up: ' + exp.message)


@operation
def stop_job(job_options, **kwargs):  # pylint: disable=W0613
    """ Stops a job in the infrastructure """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError:
        # The job wasn't configured properly, no need to be stopped
        ctx.logger.warning('Job was not stopped as it was not configured.')

    try:
        name = kwargs['name']
        is_singularity = 'croupier.nodes.SingularityJob' in ctx.node. \
            type_hierarchy

        if not simulate:
            workdir = ctx.instance.runtime_properties['workdir']
            interface_type = ctx.instance.runtime_properties['infrastructure_interface']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

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
        print(traceback.format_exc())
        ctx.logger.error(
            'Something happened when trying to stop: ' + exp.message)


def getHours(cput):
    return int(cput[:cput.index(':')])


def getMinutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def getSeconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def parseHours(cput):
    hours = getHours(cput) + getMinutes(cput) / 60.0 + getSeconds(cput) / 3600.0
    return hours


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


def report_metrics_to_monitoring(audit, workflow_id, blueprint_id, deployment_id, username, server, logger):
    try:
        if username is None:
            username = audit['job_owner']
        if 'queued_time' in audit:
            monitoring_client.publish_job_queued_time(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['queued_time'], logger)
        if 'start_time' in audit:
            monitoring_client.publish_job_execution_start_time(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['start_time'], logger)
        if 'completion_time' in audit:
            monitoring_client.publish_job_execution_completion_time(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['completion_time'], logger)
        if 'exit_status' in audit:
            monitoring_client.publish_job_execution_exit_status(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['exit_status'], logger)
        if 'cput' in audit:
            monitoring_client.publish_job_resources_used_cput(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit["cput"], logger)
        if 'cpupercent' in audit:
            monitoring_client.publish_job_resources_used_cpupercent(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['cpupercent'], logger)
        if 'ncpus' in audit:
            monitoring_client.publish_job_resources_used_ncpus(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['ncpus'], logger)
        if 'vmem' in audit:
            monitoring_client.publish_job_resources_used_vmem(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['vmem'], logger)
        if 'mem' in audit:
            monitoring_client.publish_job_resources_used_mem(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['mem'], logger)
        if 'walltime' in audit:
            monitoring_client.publish_job_resources_used_walltime(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['walltime'], logger)
        if 'mpiprocs' in audit:
            monitoring_client.publish_job_resources_requested_mpiprocs(
                blueprint_id, deployment_id, audit['job_id'], audit['job_name'], username,
                workflow_id, audit['queue'], server, audit['mpiprocs'], logger)

        # Wait 60 seconds and delete metrics (to avoid continuous sampling)
        sleep(monitoring_client.delete_after_period)
        monitoring_client.delete_metrics(audit['job_id'])

    except Exception as err:
        logger.error(
            'Statistics for job {job_id} could not be reported to Monitoring, raising an error: {err}'.
                format(job_id=audit["job_id"], err=err))


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
            username = ctx.instance.runtime_properties['credentials']['user']
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
        server = ctx.instance.runtime_properties['credentials']['host']
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
        return int(output[output.find('=')+1:].rstrip("\n"))


@operation
def publish(publish_list, data_mover_options, **kwargs):
    """ Publish the job outputs """
    try:
        simulate = ctx.instance.runtime_properties['simulate']
    except KeyError as exp:
        # The job wasn't configured properly, no need to publish
        ctx.logger.warning(
            'Job outputs where not published as' +
            ' the job was not configured properly.')
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
                        ctx.logger.error("Error using data mover: {}".format(exp.message))

            workdir = ctx.instance.runtime_properties['workdir']
            client = SshClient(ctx.instance.runtime_properties['credentials'])

            hpc_interface = ctx.instance.relationships[0].target.instance
            audit["cput"] = \
                convert_cput(audit["cput"], job_id=name, workdir=workdir, ssh_client=client,  logger=ctx.logger)
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
                        'Croupier instance not registered in Accounting'.
                            format(workflow_id=ctx.workflow_id))

            # Report metrics to Monitoring component
            if monitoring_client.report_to_monitoring:
                username = None
                infrastructure_host = None
                if hpc_interface is not None and "monitoring_options" in hpc_interface.runtime_properties:
                    monitoring_options = hpc_interface.runtime_properties["monitoring_options"]
                    if "reporting_user" in monitoring_options:
                        username = monitoring_options["reporting_user"]
                    else:
                        username = audit['job_owner']
                if hpc_interface is not None and "infrastructure_host" in hpc_interface.runtime_properties:
                    infrastructure_host = hpc_interface.runtime_properties["infrastructure_host"]
                # Report metrics to monitoring in a non-blocking call
                thread = threading.Thread(
                    target=report_metrics_to_monitoring,
                    args=(
                        audit, ctx.workflow_id, ctx.blueprint.id, ctx.deployment.id, username, infrastructure_host, ctx.logger
                    )
                )
                addThread(thread)
                thread.start()

                # report_metrics_to_monitoring(
                #     audit, ctx.blueprint.id, ctx.deployment.id, username, infrastructure_host, logger=ctx.logger)

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
            ctx.logger.info(
                'Job ' + name + ' (' + ctx.instance.id + ') published.')
        else:
            ctx.logger.error('Job ' + name + ' (' + ctx.instance.id +
                             ') not published.')
            raise NonRecoverableError('Job ' + name + ' (' + ctx.instance.id +
                                      ') not published.')
    except Exception as exp:
        print(traceback.format_exc())
        ctx.logger.error(
            'Cannot publish: ' + exp.message)
