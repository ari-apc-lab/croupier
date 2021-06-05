import logging
import os
import ConfigParser
import time
import sys

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import (
    DeploymentEnvironmentCreationPendingError,
    DeploymentEnvironmentCreationInProgressError,
    CloudifyClientError,
)

# Get an instance of a logger
LOGGER = logging.getLogger(__name__)

WAIT_FOR_EXECUTION_SLEEP_INTERVAL = 5

# workflow types

UNINSTALL = "uninstall"
INSTALL = "install"
RUN = "run_jobs"


def _get_client():
    # Configure Cloudify endpoint from configuration file
    config = ConfigParser.RawConfigParser()
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/cfi.cfg'
    print('Reading Cloudify configuration from file {file}'.format(file=config_file))
    config.read(config_file)
    client = None
    try:
        cloudify_server = config.get('Cloudify', 'host')
        cloudify_username = config.get('Cloudify', 'username')
        cloudify_password = config.get('Cloudify', 'password')
        cloudify_tenant = config.get('Cloudify', 'tenant')
        cloudify_protocol = config.get('Cloudify', 'protocol')

        client = CloudifyClient(
            host=cloudify_server,
            username=cloudify_username,
            password=cloudify_password,
            tenant=cloudify_tenant,
            protocol=cloudify_protocol,
            trust_all=True
        )
    except ConfigParser.NoSectionError:
        pass

    return client


def has_execution_ended(status):
    return status in Execution.END_STATES


def is_execution_finished(status):
    return status == Execution.TERMINATED


def is_execution_wrong(status):
    return has_execution_ended(status) and status != Execution.TERMINATED


class Cfy:
    client = None

    def __init__(self):
        self.client = _get_client()

    def list_deployments(self):
        error = None
        deployments = None
        try:
            deployments = self.client.deployments.list().items
        except CloudifyClientError as err:
            LOGGER.exception(err)
            error = str(err)

        return deployments, error

    def execute_workflow(self, deployment_id, workflow, force=False, params=None):
        error = None
        execution = None

        while True:
            try:
                execution = self.client.executions.start(
                    deployment_id, workflow, parameters=params, force=force
                )
                break
            except (
                    DeploymentEnvironmentCreationPendingError,
                    DeploymentEnvironmentCreationInProgressError,
            ) as err:
                LOGGER.warning(err)
                time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)
                continue
            except CloudifyClientError as err:
                error = str(err)
                LOGGER.exception(err)
            break

        return execution, error

    def get_execution_events(self, execution_id, offset):
        # TODO: manage errors
        cfy_execution = self.client.executions.get(execution_id)
        events = self.client.events.list(
            execution_id=execution_id, _offset=offset, _size=100, include_logs=True
        )
        last_message = events.metadata.pagination.total

        return {"logs": events.items, "last": last_message, "status": cfy_execution.status}

    def get_executions(self, deployment_id):
        result = []
        _executions = self.client.executions.list().items
        for execution in _executions:
            if execution.deployment_id == deployment_id:
                result.append(execution)
        return result

    def deployment_completed_install(self, deployment_id):
        _executions = self.get_executions(deployment_id)
        for execution in _executions:
            if execution.workflow_id == INSTALL and execution.status == "terminated":
                return True
        return False

    def get_execution_status(self, execution_id):
        # TODO: manage errors
        cfy_execution = self.client.executions.get(execution_id)

        return cfy_execution.status, cfy_execution.workflow_id


# Script code
if len(sys.argv) != 2:
    raise ValueError('usage cfy.py <deployment_id>')
deployment_id = sys.argv[1]
cfy = Cfy()
cfy.execute_workflow(deployment_id, workflow=UNINSTALL)
#if cfy.deployment_completed_install(deployment_id):
#    cfy.execute_workflow(deployment_id, workflow=RUN)
