from croupier_plugin.data_management.data_management import DataTransfer, ssh_credentials
from croupier_plugin.ssh import SshClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError


class WGetDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config):
        super().__init__(data_transfer_config)

    def process(self):
        ssh_client = None

        try:
            ctx.logger.info('Processing http data transfer')
            #  Copy source data into target data by invoking wget command at target data infrastructure
            #  Create wget command
            #  Invoke command in target infrastructure
            dt_command = None

            # Source DS
            from_source_type = self.dt_config['fromSource']['type']
            from_source_data_url = None
            if 'WebDataSource' in from_source_type:
                from_source_data_url = self.dt_config['fromSource']['properties']['resource']
            from_source_infra_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']
            if 'credentials' in self.dt_config['fromSource']['properties']['located_at']:
                from_source_infra_credentials = self.dt_config['fromSource']['properties']['located_at']['credentials']

            # Target DS
            to_target_type = self.dt_config['toTarget']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['toTarget']['properties']['filepath']
            to_target_infra_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['toTarget']['properties']['located_at']['credentials']

            credentials = ssh_credentials(to_target_infra_endpoint, to_target_infra_credentials)
            ssh_client = SshClient(credentials)

            # TODO support credentials in wget if given
            dt_command = 'wget {source_endpoint}/{resource}'.format(
                source_endpoint=
                from_source_infra_endpoint[:-1] if from_source_infra_endpoint.endswith('/')
                else from_source_infra_endpoint,
                resource=from_source_data_url[1:] if from_source_data_url.startswith('/')
                else from_source_data_url
            )

            # Execute data transfer command
            exit_msg, exit_code = ssh_client.execute_shell_command(dt_command, wait_result=True)

            if exit_code != 0:
                raise CommandExecutionError("Failed executing data transfer: exit code " + str(exit_code))

        except Exception as exp:
            raise CommandExecutionError(
                "Failed trying to connect to data source infrastructure: " + str(exp))
        finally:
            ssh_client.close_connection()
