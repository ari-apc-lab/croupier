import os

from cloudify import ctx
from croupier_plugin.ssh import SshClient, SFtpClient
from cloudify.exceptions import CommandExecutionError
import tempfile


def isOutputRelationship(relationship):
    return 'output' == relationship._relationship['type']


def isFromSourceRelationship(relationship):
    return 'from_source' == relationship._relationship['type']


def isToTargetRelationship(relationship):
    return 'to_target' == relationship._relationship['type']


def isDataManagementNode(node):
    return not ('croupier.nodes.Job' in node.type_hierarchy or
                'croupier.nodes.InfrastructureInterface' in node.type_hierarchy)


def isDataTransferNode(node):
    return 'croupier.nodes.DataTransfer' in node.type_hierarchy


def isDataManagementRelationship(relationship):
    return ('input' == relationship._relationship['type'] or
            'output' == relationship._relationship['type'])


def findDataTransferInstancesForSource(data_source, nodes):
    #  find data transfer object in nodes, such as DT|from-source == DS node
    dt_instances = []
    for node in nodes:
        if isDataTransferNode(node):
            for relationship in node.relationships:
                if isFromSourceRelationship(relationship):
                    if data_source.id == relationship.target_node.id:
                        dt_instances.append(node)
    return dt_instances


def createDataSourceNode(output, dt_instances=None):
    dsNode = {}
    dsNode['id'] = output.id
    dsNode['type'] = output.type
    dsNode['properties'] = output.properties
    data_transfer_instances = []
    if dt_instances:
        for dt_instance in dt_instances:
            data_transfer_instances.append(createDataTransferNode(dt_instance))
    dsNode['dt_instances'] = data_transfer_instances
    return dsNode


def createDataTransferNode(dt_instance):
    dtNode = {}
    dtNode['id'] = dt_instance.id
    dtNode['transfer_protocol'] = dt_instance.properties['transfer_protocol']
    for relationship in dt_instance.relationships:
        if isFromSourceRelationship(relationship):
            dtNode['fromSource'] = createDataSourceNode(relationship.target_node)
        if isToTargetRelationship(relationship):
            dtNode['toTarget'] = createDataSourceNode(relationship.target_node)
    return dtNode


def ssh_credentials(host, dm_credentials):
    credentials = {}
    credentials['host'] = host
    credentials['user'] = dm_credentials['username']
    if 'password' in dm_credentials:
        credentials['password'] = dm_credentials['password']
    if 'key' in dm_credentials:
        credentials['private_key'] = dm_credentials['key']
    if 'key_password' in dm_credentials:
        credentials['private_key_password'] = dm_credentials['key_password']

    return credentials


def processDataTransfer(outputs):
    # For each output in outputs
    # For each data transfer object in output
    # execute data_transfer
    # TODO parallel processing of data transfer
    for output in outputs:
        if 'dt_instances' in output:
            for dt_config in output['dt_instances']:
                dt = DataTransfer.factory(dt_config)
                dt.process()


class DataTransfer:
    def __init__(self, data_transfer_config):
        self.dt_config = data_transfer_config
        # Based on data transfer type, use the Factory to create an specialized DataTransfer instance

    @staticmethod
    def factory(dt_config):
        if dt_config['transfer_protocol'].upper() == "RSYNC":
            return RSyncDataTransfer(dt_config)

    def process(self):
        raise NotImplementedError(
            "'process' not implemented.")


class RSyncDataTransfer:
    def __init__(self, data_transfer_config):
        self.dt_config = data_transfer_config

    def process(self):
        ssh_client = None
        ftp_client = None

        try:
            ctx.logger.info('Processing data transfer')
            #  Copy source data into target data by invoking rsync command at target data infrastructure
            #  Create rsync command (check available credentials for target data infrastructure)
            #  If credential include user/password, rsync command is:
            #  rsync -ratlz --rsh="/usr/bin/sshpass -p <passwd> ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l <user>" <source files to copy>  <HPC remote server>:<target folder>
            #  If credential include user/key, rsync command is:
            #  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -i <key_file>"  <files to copy>  <user>@<HPC remote server>:<target folder>
            #  Copy key in temporary file and destroy it (whatsoever) after usage (or failure)
            #  Invoke command in target infrastructure
            dt_command = None
            key_file = None

            # Source DS
            from_source_type = self.dt_config['fromSource']['type']
            from_source_data_url = None
            if 'FileDataSource' in from_source_type:
                from_source_data_url = self.dt_config['fromSource']['properties']['filepath']
            from_source_infra_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']
            from_source_infra_credentials = self.dt_config['fromSource']['properties']['located_at']['credentials']

            # Target DS
            to_target_type = self.dt_config['toTarget']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['toTarget']['properties']['filepath']
            to_target_infra_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['toTarget']['properties']['located_at']['credentials']

            credentials = ssh_credentials(from_source_infra_endpoint, from_source_infra_credentials)
            ssh_client = SshClient(credentials)
            ftp_client = SFtpClient(credentials)

            if "username" in to_target_infra_credentials and "password" in to_target_infra_credentials:
                target_username = to_target_infra_credentials['username']
                target_password = to_target_infra_credentials['password']
                dt_command = 'rsync -ratlz --rsh="/usr/bin/sshpass -p {password} ssh -o StrictHostKeyChecking=no -o ' \
                             'IdentitiesOnly=yes -l {username}" {ds_source}  {target_endpoint}:{ds_target}'.format(
                    username=target_username, password=target_password, target_endpoint=to_target_infra_endpoint,
                    ds_source=from_source_data_url, ds_target=to_target_data_url
                )
            elif "username" in to_target_infra_credentials and "key" in to_target_infra_credentials:
                target_username = to_target_infra_credentials['username']
                target_key = to_target_infra_credentials['key']
                # Save key in temporary file
                with tempfile.NamedTemporaryFile() as key_file:
                    key_file.write(bytes(target_key, 'utf-8'))
                    key_file.flush()
                    key_filepath = key_file.name
                    target_key_filepath = key_file.name.split('/')[-1]
                    # Transfer key_file
                    ftp_client.sendKeyFile(ssh_client, key_filepath, target_key_filepath)
                    dt_command = 'rsync -ratlz -e "ssh -o IdentitiesOnly=yes -i {key_file}"  {ds_source}  {username}@{' \
                                 'target_endpoint}:{ds_target}'.format(
                        username=target_username, key_file=target_key_filepath, target_endpoint=to_target_infra_endpoint,
                        ds_source=from_source_data_url, ds_target=to_target_data_url
                    )

            # Execute data transfer command
            exit_msg, exit_code = ssh_client.execute_shell_command(dt_command, wait_result=True)

            if exit_code != 0:
                raise CommandExecutionError("Failed executing data transfer: exit code " + str(exit_code))

        except Exception as exp:
            raise CommandExecutionError(
                "Failed trying to connect to data source infrastructure: " + str(exp))
        finally:
            if target_key_filepath:
                # TODO Remove remote key temporary file
                #   Investigate how to execute data transfer without copying the key file remotely
                ftp_client.removeFile(target_key_filepath)
            ftp_client.close_connection()
            ssh_client.close_connection()

# Test


dt_config = {
    'id': 'dt1',
    'transfer_protocol': 'RSync',
    'fromSource': {
        'id': 'out1',
        'type': 'croupier.nodes.FileDataSource',
        'properties': {
            'filepath': '~/Next_trials_ITAINNOVA.zip',
            'located_at': {
                'endpoint': 'ft2.cesga.es',
                'supported_protocols': ['SCP', 'Filesystem', 'RSync'],
                'credentials': {
                    'username': 'otgatjgc',
                    'password': 'ot.4.jgc'
                }
            }
        },
        'dt_instances': []
    },
    'toTarget': {
        'id': 'in4',
        'type': 'croupier.nodes.FileDataSource',
        'properties': {
            'filepath': '~/test/',
            'located_at': {
                'endpoint': 'sodalite-fe.hlrs.de',
                'supported_protocols': ['Filesystem', 'RSync'],
                'credentials': {
                    'username': 'yosu',
                    'key': 'key content ...'
                }
            }
        },
        'dt_instances': []
    }
}

# dt = DataTransfer.factory(dt_config)
# dt.process()
