from croupier_plugin.data_management.data_management import DataTransfer, ssh_credentials
from croupier_plugin.ssh import SshClient, SFtpClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError
import tempfile


class RSyncDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config):
        super().__init__(data_transfer_config)

    def process(self):
        ssh_client = None
        ftp_client = None

        try:
            ctx.logger.info('Processing rsync data transfer')
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
                # NOTE rsync authentication with username/password requires sshpass which it is not installed
                # some HPC frontends
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
                    dt_command = 'rsync -ratlz -e "ssh -o IdentitiesOnly=yes -i {key_file}"  {ds_source}  ' \
                                 '{username}@{target_endpoint}:{ds_target}'.format(
                        username=target_username, key_file=target_key_filepath,
                        target_endpoint=to_target_infra_endpoint,
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
