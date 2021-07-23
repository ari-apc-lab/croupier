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

workflows.py - Holds the plugin workflows
'''

import sys
import time

from cloudify.decorators import workflow
from cloudify.workflows import ctx, api, tasks
from croupier_plugin.job_requester import JobRequester

from uuid import uuid1 as uuid

LOOP_PERIOD = 1
DB_JOBID = {}


class JobGraphInstance(object):
    """ Wrap to add job functionalities to node instances """

    def __init__(self, parent, instance, pseudo_deployment_id):
        self._status = 'WAITING'
        self.parent_node = parent
        self.winstance = instance

        self.completed = not self.parent_node.is_job  # True if is not a job
        self.failed = False
        self.audit = None
        self.pseudo_deployment_id = pseudo_deployment_id

        if parent.is_job:
            self._status = 'WAITING'
            self.jobid = ''
            # Get runtime properties
            runtime_properties = instance._node_instance.runtime_properties
            ctx.logger.info("runtime_properties:" + str(runtime_properties))
            self.simulate = runtime_properties["simulate"]
            self.host = runtime_properties["credentials"]["host"]
            self.workdir = runtime_properties['workdir']

            # Decide how to monitor the job
            if runtime_properties["external_monitor_entrypoint"]:
                self.monitor_type = runtime_properties["external_monitor_type"]
                self.monitor_config = {
                    'url': ('http://' +
                            runtime_properties["external_monitor_entrypoint"] +
                            runtime_properties["external_monitor_port"])
                }
            else:  # internal monitoring
                self.monitor_type = runtime_properties["infrastructure_interface"]
                self.monitor_config = runtime_properties["credentials"]

            self.monitor_period = int(runtime_properties["monitor_period"])

            # build job name
            instance_components = instance.id.split('_')
            self.name = runtime_properties["job_prefix"] + "_".join(instance_components[:-1])

        else:
            self._status = 'NONE'
            self.name = instance.id
            self.monitor_url = ""

    def queue(self, monitor):
        """ Sends the job's instance to the infrastructure queue """
        if not self.parent_node.is_job:
            return

        self.winstance.send_event('Queuing job..')
        result = self.winstance.execute_operation('croupier.interfaces.lifecycle.queue',
                                                  kwargs={"name": self.name,
                                                          "pseudo_deployment_id": self.pseudo_deployment_id})
        # result.task.wait_for_terminated()
        result.get()
        if result.task.get_state() == tasks.TASK_FAILED:
            init_state = 'FAILED'
        else:
            self.winstance.send_event('.. job queued')
            init_state = 'PENDING'
        self.set_status(init_state)
        self.jobid = DB_JOBID[self.pseudo_deployment_id][self.name]
        ctx.logger.info("Jobid saved is: " + self.jobid)
        monitor.register_jobid(self.jobid, self.name)
        return result

    def publish(self):
        """ Publish the job's instance outputs """
        if not self.parent_node.is_job:
            return

        self.winstance.send_event('Publishing job outputs..')
        result = self.winstance.execute_operation('croupier.interfaces.'
                                                  'lifecycle.publish',
                                                  kwargs={"name": self.name, "jobid": self.jobid, "audit": self.audit})
        # result.task.wait_for_terminated()
        result.get()
        if result.task.get_state() != tasks.TASK_FAILED:
            self.winstance.send_event('..outputs sent for publication')

        return result.task

    def set_status(self, status):
        """ Update the instance state """
        if not status == self._status:
            self._status = status
            self.winstance.send_event('State changed to ' + self._status)

            self.completed = not self.parent_node.is_job or \
                self._status == 'COMPLETED'

            if self.completed:
                self.publish()

            if not self.parent_node.is_job:
                self.failed = False
            else:
                self.failed = self.parent_node.is_job and \
                    (self._status == 'BOOT_FAIL' or
                     self._status == 'CANCELLED' or
                     self._status == 'FAILED' or
                     self._status == 'REVOKED' or
                     self._status == 'TIMEOUT')

    def clean(self):
        """ Cleans job's aux files """
        if not self.parent_node.is_job:
            return

        self.winstance.send_event('Cleaning job..')
        result = self.winstance.execute_operation('croupier.interfaces.'
                                                  'lifecycle.cleanup',
                                                  kwargs={"name": self.name})
        # result.task.wait_for_terminated()
        self.winstance.send_event('.. job cleaned')

        # print result.task.dump()
        return result.task

    def cancel(self):
        """ Cancels the job instance in the infrastructure """
        if not self.parent_node.is_job:
            return

        # First perform clean operation
        self.clean()

        self.winstance.send_event('Cancelling job..')
        result = self.winstance.execute_operation('croupier.interfaces.'
                                                  'lifecycle.cancel',
                                                  kwargs={"name": self.name, "jobid": self.jobid})
        self.winstance.send_event('.. job canceled')
        result.get()
        # result.task.wait_for_terminated()

        self._status = 'CANCELLED'

    @staticmethod
    def register_jobid(pseudo_deployment_id, name, jobid):
        if pseudo_deployment_id not in DB_JOBID:
            DB_JOBID[pseudo_deployment_id] = {}
        DB_JOBID[pseudo_deployment_id][name] = jobid


class JobGraphNode(object):
    """ Wrap to add job functionalities to nodes """

    def __init__(self, node, job_instances_map, pseudo_deployment_id):
        self.name = node.id
        self.type = node.type
        self.cfy_node = node
        self.is_job = 'croupier.nodes.Job' in node.type_hierarchy

        if self.is_job:
            self.status = 'WAITING'
        else:
            self.status = 'NONE'

        self.instances = []
        for instance in node.instances:
            graph_instance = JobGraphInstance(self,
                                              instance, pseudo_deployment_id)
            self.instances.append(graph_instance)
            if graph_instance.parent_node.is_job:
                job_instances_map[graph_instance.name] = graph_instance

        self.parents = []
        self.children = []
        self.parent_depencencies_left = 0

        self.completed = False
        self.failed = False

    def add_parent(self, node):
        """ Adds a parent node """
        self.parents.append(node)
        self.parent_depencencies_left += 1

    def add_child(self, node):
        """ Adds a child node """
        self.children.append(node)

    def queue_all_instances(self, monitor):
        """ Sends all job instances to the infrastructure queue """
        if not self.is_job:
            return []

        tasks_result_list = []
        for job_instance in self.instances:
            tasks_result_list.append(job_instance.queue(monitor))

        self.status = 'QUEUED'
        return tasks_result_list

    def is_ready(self):
        """ True if it has no more dependencies to satisfy """
        return self.parent_depencencies_left == 0

    def _remove_children_dependency(self):
        """ Removes a dependency of the Node already satisfied """
        for child in self.children:
            child.parent_depencencies_left -= 1

    def check_status(self):
        """
        Check if all instances status

        If all of them have finished, change node status as well
        Returns True if there is no errors (no job has failed)
        """
        if not self.completed and not self.failed:
            if not self.is_job:
                self._remove_children_dependency()
                self.status = 'COMPLETED'
                self.completed = True
            else:
                completed = True
                failed = False
                for job_instance in self.instances:
                    if job_instance.failed:
                        failed = True
                        break
                    elif not job_instance.completed:
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
        readys = []
        for child in self.children:
            if child.is_ready():
                readys.append(child)
        return readys

    def __str__(self):
        to_print = self.name + '\n'
        for instance in self.instances:
            to_print += '- ' + instance.name + '\n'
        for child in self.children:
            to_print += '    ' + child.name + '\n'
        return to_print

    def clean_all_instances(self):
        """ Cleans all job's files instances of the infrastructure """
        if not self.is_job:
            return

        for job_instance in self.instances:
            job_instance.clean()
        self.status = 'CANCELED'

    def cancel_all_instances(self):
        """ Cancels all job instances of the infrastructure """
        if not self.is_job:
            return

        for job_instance in self.instances:
            job_instance.cancel()
        self.status = 'CANCELED'


def build_graph(nodes, pseudo_deployment_id ):
    """ Creates a new graph of nodes and instances with the job wrapper """

    job_instances_map = {}

    # first create node structure
    nodes_map = {}
    root_nodes = []
    for node in nodes:
        new_node = JobGraphNode(node, job_instances_map, pseudo_deployment_id)
        nodes_map[node.id] = new_node
        # check if it is root node
        try:
            node.relationships.next()
        except StopIteration:
            root_nodes.append(new_node)

    # then set relationships
    for _, child in nodes_map.iteritems():
        for relationship in child.cfy_node.relationships:
            parent = nodes_map[relationship.target_node.id]
            parent.add_child(child)
            child.add_parent(parent)

    return root_nodes, job_instances_map


class Monitor(object):
    """Monitor the instances"""

    MAX_ERRORS = 5

    def __init__(self, job_instances_map, logger):
        self._execution_pool = {}
        self.timestamp = 0
        self.job_instances_map = job_instances_map
        self.job_instances_map_jobid = {}
        self.logger = logger
        self.jobs_requester = JobRequester()
        self.continued_errors = 0

    def update_status(self):
        """Gets all executing instances and update their state"""

        # first get the instances we need to check
        monitor_jobs = {}
        for _, job_node in self.get_executions_iterator():
            if job_node.is_job:
                for job_instance in job_node.instances:
                    if not job_instance.simulate:
                        if job_instance.host in monitor_jobs:
                            monitor_jobs[job_instance.host]['jobids'].append(
                                job_instance.jobid)
                        else:
                            monitor_jobs[job_instance.host] = {
                                'config': job_instance.monitor_config,
                                'type': job_instance.monitor_type,
                                'workdir': job_instance.workdir,
                                'jobids': [job_instance.jobid],
                                'period': job_instance.monitor_period
                            }
                    else:
                        job_instance.set_status('COMPLETED')

        # nothing to do if we don't have nothing to monitor
        if not monitor_jobs:
            return

        # then look for the status of the instances through its name
        try:
            states, audits = self.jobs_requester.request(monitor_jobs, self.logger)

            # set job audit
            for jobid, audit in audits.iteritems():
                self.job_instances_map_jobid[jobid].audit = audit

            # finally set job status
            for jobid, state in states.iteritems():
                self.job_instances_map_jobid[jobid].set_status(state)

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
        return self._execution_pool.iteritems()

    def add_node(self, node):
        """ Adds a node to the execution pool """
        self._execution_pool[node.name] = node

    def finish_node(self, node_name):
        """ Delete a node from the execution pool """
        del self._execution_pool[node_name]

    def is_something_executing(self):
        """ True if there are nodes executing """
        return self._execution_pool

    def register_jobid(self, jobid, name):
        """ Registers the jobid to an instance by name """
        self.job_instances_map_jobid[jobid] = self.job_instances_map[name]


@workflow
def run_jobs(**kwargs):  # pylint: disable=W0613
    """ Workflow to execute long running batch operations """
    pseudo_deployment_id = str(uuid())
    DB_JOBID[pseudo_deployment_id] = {}
    root_nodes, job_instances_map = build_graph(ctx.nodes, pseudo_deployment_id)
    monitor = Monitor(job_instances_map, ctx.logger)

    # Execution of first job instances
    task_result_list = []
    for root in root_nodes:
        task_result_list += root.queue_all_instances(monitor)
        monitor.add_node(root)
    wait_tasks_to_finish(task_result_list)

    # Monitoring and next executions loop
    while monitor.is_something_executing() and not api.has_cancel_request():
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
        # perform new executions
        tasks_result_list = []
        for new_node in new_exec_nodes:
            tasks_result_list += new_node.queue_all_instances(monitor)
            monitor.add_node(new_node)
        wait_tasks_to_finish(tasks_result_list)

    if monitor.is_something_executing():
        cancel_all(monitor.get_executions_iterator())

    ctx.logger.info(
        "------------------Workflow Finished-----------------------")
    return


def cancel_all(executions):
    """Cancel all pending or running jobs"""
    for _, exec_node in executions:
        exec_node.cancel_all_instances()
    raise api.ExecutionCancelled()


def wait_tasks_to_finish(tasks_result_list):
    """Blocks until all tasks have finished"""
    for result in tasks_result_list:
        result.get()
        # task.wait_for_terminated()
