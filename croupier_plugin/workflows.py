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

workflows.py - Holds the plugin workflows
"""
import os

import configparser
from builtins import next
from builtins import str
from builtins import object
import sys
import time
from datetime import datetime

from cloudify.decorators import workflow
from cloudify.workflows import ctx, api, tasks
from cloudify.plugins.workflows import install
from croupier_plugin.job_requester import JobRequester
from croupier_plugin.vault.vault import revoke_token

LOOP_PERIOD = 1


class GraphInstance(object):

    def __init__(self, parent, instance):
        self._status = 'NONE'
        self.name = instance.id
        self.monitor_url = ""
        self.instance = instance
        self.node = parent
        self.completed = True
        self.failed = False
        self.audit = {}
        self.runtime_properties = instance._node_instance.runtime_properties

    def launch(self):
        pass

    def set_status(self, status):
        """ Update the instance state """
        if not status == self._status:
            self._status = status
            self.instance.send_event('State changed to ' + self._status)

            self.completed = self._status == 'COMPLETED'

            self.failed = (self._status == 'BOOT_FAIL' or
                           self._status == 'CANCELLED' or
                           self._status == 'FAILED' or
                           self._status == 'REVOKED' or
                           self._status == 'TIMEOUT')

    def update_properties(self):
        self.runtime_properties = self.instance._node_instance.runtime_properties


class TaskGraphInstance(GraphInstance):
    def __init__(self, parent, instance):
        super().__init__(parent, instance)
        self.instance = instance
        self._status = 'WAITING'
        self.completed = False


class JobGraphInstance(TaskGraphInstance):
    """ Wrap to add job functionalities to node instances """

    def __init__(self, parent, instance):
        super().__init__(parent, instance)

        # Get runtime properties
        self.host = self.runtime_properties["ssh_config"]["host"]
        self.simulate = self.runtime_properties["simulate"]
        self.workdir = self.runtime_properties["workdir"]
        self.monitor_type = self.runtime_properties["infrastructure_interface"]
        self.monitor_config = self.runtime_properties["ssh_config"]

        monitoring_options = self.runtime_properties["monitoring_options"]
        self.monitor_period = int(monitoring_options["monitor_period"]) if "monitor_period" in monitoring_options \
            else 10
        self.reservation = self.node.cfy_node.properties["job_options"]["reservation"] \
            if "reservation" in self.node.cfy_node.properties["job_options"] else ""
        self.name = self.runtime_properties["job_prefix"] + self.instance.id

    def launch(self):
        """ Sends the job's instance to the infrastructure queue """
        self.instance.send_event('Queuing job..')
        result = self.instance.execute_operation('croupier.interfaces.lifecycle.queue', kwargs={"name": self.name})
        result.get()
        if result.task.get_state() == tasks.TASK_FAILED:
            init_state = 'FAILED'
        else:
            self.instance.send_event('.. job queued')
            init_state = 'PENDING'
        self.set_status(init_state)
        return result

    def delete_reservation(self):
        """ Sends the job's instance to the infrastructure queue """
        self.update_properties()
        self.instance.send_event('Deleting reservation...')
        result = self.instance.execute_operation('croupier.interfaces.lifecycle.delete_reservation',
                                                 kwargs={"name": self.name})
        result.get()

    def publish(self):
        """ Publish the job's instance outputs """

        self.instance.send_event('Publishing job outputs..')
        result = self.instance.execute_operation('croupier.interfaces.lifecycle.publish',
                                                 kwargs={"name": self.name, "audit": self.audit})
        result.get()
        if result.task.get_state() != tasks.TASK_FAILED:
            self.instance.send_event('..outputs sent for publication')

        return result.task

    def set_status(self, status):
        """ Update the instance state """
        before = self.completed
        super().set_status(status)

        if self.completed and not before:
            self.publish()

    def clean(self):
        """ Cleans job's aux files """

        self.instance.send_event('Cleaning job..')
        result = self.instance.execute_operation('croupier.interfaces.lifecycle.cleanup',
                                                 kwargs={"name": self.name})

        self.instance.send_event('.. job cleaned')

        return result.task

    def cancel(self):
        """ Cancels the job instance in the infrastructure """
        # First perform clean operation
        self.clean()

        self.instance.send_event('Cancelling job..')
        result = self.instance.execute_operation('croupier.interfaces.lifecycle.cancel',
                                                 kwargs={"name": self.name})
        self.instance.send_event('.. job canceled')
        result.get()

        self._status = 'CANCELLED'


class DataGraphInstance(TaskGraphInstance):

    def __init__(self, parent, instance):

        super().__init__(parent, instance)
        self.name = instance.id
        self.completed = False
        self.source_urls = self.runtime_properties['data_urls'] \
            if 'data_urls' in self.runtime_properties else []
        ctx.logger.info(self.source_urls)

    def launch(self):
        self.instance.execute_operation('cloudify.interfaces.delete')
        """ Launches the data gathering algorithm """
        self.instance.send_event('Launched gathering data process...')
        result = self.instance.execute_operation('cloudify.interfaces.lifecycle.configure')
        result.get()
        if result.task.get_state() == tasks.TASK_FAILED:
            init_state = 'FAILED'
        else:
            self.instance.send_event('.. Gathering data')
            init_state = 'PENDING'
        self.set_status(init_state)
        return result

    def update_properties(self):
        super().update_properties()
        self.source_urls = self.runtime_properties['data_urls'] \
            if 'data_urls' in self.runtime_properties else []


class GraphNode(object):
    """ Wrap to add job functionalities to nodes """

    def __init__(self, node, job_instances_map):
        self.name = node.id
        self.type = node.type
        self.cfy_node = node
        self.is_job = 'croupier.nodes.Job' in node.type_hierarchy
        self.is_data = 'croupier.nodes.Data' in node.type_hierarchy
        self.is_task = self.is_job or self.is_data
        self.completed = False
        self.failed = False
        self.parents = []
        self.children = []
        self.parent_dependencies_left = 0
        if self.is_task:
            self.status = 'WAITING'
        else:
            self.status = 'NONE'

        self.instances = []
        for instance in node.instances:

            if self.is_job:
                graph_instance = JobGraphInstance(self, instance)
                job_instances_map[graph_instance.name] = graph_instance
            elif self.is_data:
                graph_instance = DataGraphInstance(self, instance)
            else:
                graph_instance = GraphInstance(self, instance)

            self.instances.append(graph_instance)

    def add_parent(self, node):
        """ Adds a parent node """
        self.parents.append(node)
        self.parent_dependencies_left += 1

    def add_child(self, node):
        """ Adds a child node """
        self.children.append(node)

    def launch_all_instances(self):
        """ Launches all task instances """
        tasks_result_list = []
        if self.is_task:
            for task_instance in self.instances:
                tasks_result_list.append(task_instance.launch())
            self.status = 'QUEUED'

        return tasks_result_list

    def is_ready(self):
        """ True if it has no more dependencies to satisfy """
        return self.parent_dependencies_left == 0

    def _remove_children_dependency(self):
        """ Removes a dependency of the Node already satisfied """
        for child in self.children:
            child.parent_dependencies_left -= 1

    def check_status(self):
        """
        Check if all instances status

        If all of them have finished, change node status as well
        Returns True if there is no errors (no job has failed)
        """
        if not self.completed and not self.failed:
            if not self.is_task:
                self._remove_children_dependency()
                self.status = 'COMPLETED'
                self.completed = True
            else:
                completed = True
                failed = False
                for instance in self.instances:
                    if instance.failed:
                        failed = True
                        break
                    elif not instance.completed:
                        completed = False

                if failed:
                    self.status = 'FAILED'
                    self.failed = True
                    self.completed = False
                    return False

                if completed:
                    # The job node just finished, remove this dependency
                    self.status = 'COMPLETED'
                    self._remove_children_dependency()
                    self.completed = True

        return not self.failed

    def get_children_ready(self):
        """ Gets all children nodes that are ready to start """
        ready = []
        for child in self.children:
            if child.is_ready():
                ready.append(child)
        return ready

    def __str__(self):
        to_print = self.name + '\n'
        for instance in self.instances:
            to_print += '- ' + instance.name + '\n'
        for child in self.children:
            to_print += '    ' + str(child) + '\n'
        return to_print

    def clean_all_instances(self):
        """ Cleans all job's files instances of the infrastructure """
        if not self.is_job:
            return

        for job_instance in self.instances:
            job_instance.clean()
        self.status = 'CANCELLED'

    def cancel_all_instances(self):
        """ Cancels all job instances of the infrastructure """
        if not self.is_job:
            return

        for job_instance in self.instances:
            job_instance.cancel()
        self.status = 'CANCELLED'


class Monitor(object):
    """Monitor the instances"""

    MAX_ERRORS = 5

    def __init__(self, job_instances_map, logger):
        self._execution_pool = {}
        self.timestamp = 0
        self.job_instances_map = job_instances_map
        self.logger = logger
        self.jobs_requester = JobRequester()
        self.continued_errors = 0
        self.monitor_start_time = datetime.now()

    def update_status(self):
        """Gets all executing instances and update their state"""

        # first get the instances we need to check
        monitor_jobs = {}
        for _, task_node in self.get_executions_iterator():
            if task_node.is_job:
                for job_instance in task_node.instances:
                    if not job_instance.simulate:
                        if job_instance.host in monitor_jobs:
                            monitor_jobs[job_instance.host]['names'].append(
                                job_instance.name)
                        else:
                            monitor_jobs[job_instance.host] = {
                                'config': job_instance.monitor_config,
                                'type': job_instance.monitor_type,
                                'workdir': job_instance.workdir,
                                'names': [job_instance.name],
                                'period': job_instance.monitor_period
                            }
                    else:
                        job_instance.set_status('COMPLETED')
            elif task_node.is_data:
                for data_instance in task_node.instances:
                    data_instance.update_properties()
                    if data_instance.source_urls:
                        data_instance.set_status('COMPLETED')

        # nothing to do if we don't have nothing to monitor
        if not monitor_jobs:
            return

        # then look for the status of the instances through its name
        try:
            states, audits = self.jobs_requester.request(monitor_jobs, self.monitor_start_time, self.logger)

            # set job audit
            for inst_name, audit in audits.items():
                self.job_instances_map[inst_name].audit = audit

            # finally set job status
            for inst_name, state in states.items():
                self.job_instances_map[inst_name].set_status(state)

            self.continued_errors = 0
        except Exception as exp:
            if self.continued_errors >= Monitor.MAX_ERRORS:
                self.logger.error("Error when monitoring jobs: " + str(exp))
                raise exp
            else:
                self.continued_errors += 1
                count = str(self.continued_errors)+"/"+str(Monitor.MAX_ERRORS)
                self.logger.warning("Error when monitoring jobs ("+count+"): " + str(exp))

        # We wait to slow down the loop
        sys.stdout.flush()  # necessary to output work properly with sleep
        time.sleep(LOOP_PERIOD)

    def get_executions_iterator(self):
        """ Executing nodes iterator """
        return self._execution_pool.items()

    def add_node(self, node):
        """ Adds a node to the execution pool """
        self._execution_pool[node.name] = node

    def finish_node(self, node_name):
        """ Delete a node from the execution pool """
        del self._execution_pool[node_name]

    def is_something_executing(self):
        """ True if there are nodes executing """
        return self._execution_pool


def build_graph(nodes):
    """ Creates a new graph of nodes and instances with the job wrapper """

    job_instances_map = {}

    # first create node structure
    nodes_map = {}
    root_nodes = []
    for node in nodes:
        new_node = GraphNode(node, job_instances_map)
        nodes_map[node.id] = new_node
        # check if it is root node
        try:
            next(node.relationships)
        except StopIteration:
            root_nodes.append(new_node)

    # then set relationships
    for _, child in nodes_map.items():
        for relationship in child.cfy_node.relationships:
            parent = nodes_map[relationship.target_node.id]
            parent.add_child(child)
            child.add_parent(parent)

    return root_nodes, job_instances_map


class ConfigureInterface(object):
    def __init__(self, node):
        self.instances = node.instances

    def configure(self):
        for instance in self.instances:
            result = instance.execute_operation('configure', kwargs={"recurring": True})
            result.get()


class ConfigureTask(object):
    def __init__(self, node):
        self.instances = node.instances

    def configure(self):
        for instance in self.instances:
            for relationship_instance in instance.relationships:
                result_preconfigure = relationship_instance.execute_source_operation('preconfigure',
                                                                                     kwargs={"recurring": True})
                result_preconfigure.get()
            result_configure = instance.execute_source_operation('configure', kwargs={"recurring": True})
            result_configure.get()


def build_configure_graph(nodes):
    jobs = []
    interfaces = []
    for node in nodes:
        if 'croupier.nodes.InfrastructureInterface' in node.type_hierarchy:
            interfaces.append(ConfigureInterface(node))
        elif 'croupier.nodes.Job' or 'croupier.nodes.Data' in node.type_hierarchy:
            jobs.append(ConfigureTask(node))

    return jobs, interfaces


def execute_jobs(force_data, skip_jobs, **kwargs):  # pylint: disable=W0613
    """ Workflow to execute long running batch operations """
    root_nodes, job_instances_map = build_graph(ctx.nodes)
    monitor = Monitor(job_instances_map, ctx.logger)

    new_exec_nodes = root_nodes

    # Monitoring and next executions loop
    while new_exec_nodes or monitor.is_something_executing() and not api.has_cancel_request():
        # perform new executions
        tasks_result_list = []
        for new_node in new_exec_nodes:
            monitor.add_node(new_node)
            if (force_data or not new_node.is_data) and (not new_node.is_job or not skip_jobs):
                tasks_result_list += new_node.launch_all_instances()

        wait_tasks_to_finish(tasks_result_list)
        # Monitor the infrastructure
        monitor.update_status()
        exec_nodes_finished = []
        new_exec_nodes = []
        for node_name, exec_node in monitor.get_executions_iterator():
            if exec_node.check_status():
                if exec_node.completed:
                    exec_node.clean_all_instances()
                    exec_nodes_finished.append(node_name)
                    new_nodes_to_execute = exec_node.get_children_ready()
                    for new_node in new_nodes_to_execute:
                        new_exec_nodes.append(new_node)
            else:
                # Something went wrong in the node, cancel execution
                cancel_all(monitor.get_executions_iterator())
                return

        # remove finished nodes
        for node_name in exec_nodes_finished:
            monitor.finish_node(node_name)

        wait_tasks_to_finish(tasks_result_list)

    if monitor.is_something_executing():
        ctx.logger.info("Cancelling jobs...")
        cancel_all(monitor.get_executions_iterator())

    deleted_reservations = []
    for instance_name in job_instances_map:
        instance = job_instances_map[instance_name]
        if instance.reservation not in deleted_reservations and instance.reservation:
            instance.delete_reservation()
            deleted_reservations.append(instance.reservation)

    ctx.logger.info("------------------Workflow Finished-----------------------")
    return


@workflow
def croupier_install(**kwargs):

    # deployment_id = ctx.nodes[0].properties['resource_config']['deployment']['id']
    # rest_client = get_rest_client()
    # rest_client.executions.start(deployment_id, "install")

    install(ctx)

    vault_tokens = {}
    config = configparser.RawConfigParser()
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/Croupier.cfg'
    config.read(config_file)
    try:
        default_vault_address = config.get('Vault', 'vault_address')
        if default_vault_address is None:
            ctx.logger.error('Could not find vault_address in the Vault section of the croupier config file.'
                             ' Did not revoke token')
            return
    except configparser.NoSectionError:
        ctx.logger.error('Could not find the Vault section in the croupier config file. Did not revoke token')
        return

    for node in ctx.nodes:
        if 'croupier.nodes.Vault' in node.type_hierarchy:
            address = node.properties['address'] if node.properties['address'] else default_vault_address
            address = address if address.startswith("http") else "http://" + address
            vault_tokens[address] = node.properties['token']

    for vault_address in vault_tokens:

        error = revoke_token(vault_tokens[vault_address], vault_address)
        if error:
            ctx.logger.error("Could not revoke vault token from " + vault_address +
                             "\n Status code: " + str(error["error"]) +
                             "\n Content: " + str(error["content"]))

        else:
            ctx.logger.info("Token from " + vault_address + "successfully revoked")

    if not vault_tokens:
        ctx.logger.warning("Could not find any tokens to revoke")
    ctx.logger.info("------------------Workflow Finished-----------------------")


@workflow
def croupier_configure(**kwargs):
    job_instances, interface_instances = build_configure_graph(ctx.nodes)

    for interface in interface_instances:
        interface.configure()

    for job in job_instances:
        job.configure()


def cancel_all(executions):
    """Cancel all pending or running jobs"""
    for _, exec_node in executions:
        exec_node.cancel_all_instances()
    raise api.ExecutionCancelled()


def wait_tasks_to_finish(tasks_result_list):
    """Blocks until all tasks have finished"""
    for result in tasks_result_list:
        result.get()


@workflow
def run_jobs(**kwargs):  # pylint: disable=W0613
    execute_jobs(force_data=False, skip_jobs=False)


# TODO: Implement these workflows properly

"""
@workflow
def gather_data(**kwargs):  # pylint: disable=W0613
    execute_jobs(force_data=True, skip_jobs=True, **kwargs)


@workflow
def run_jobs_force_get_data(**kwargs):  # pylint: disable=W0613
    execute_jobs(force_data=True, skip_jobs=False)
"""






