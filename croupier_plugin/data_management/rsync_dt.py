from croupier_plugin.data_management.data_management import DataTransfer, ssh_credentials
from croupier_plugin.ssh import SshClient, SFtpClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError
import tempfile
import os


class RSyncDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config):
        super().__init__(data_transfer_config)

    def process(self):
        if self.dt_config['fromSource']:
            self.process_rsync_transfer_with_proxy()
        else:
            self.process_rsync_transfer()

    '''
        Rsync data transfer executed from Croupier server
        Requires sshfs command available (install sshfs package)
        Requires ssh key-based access to both source and target data servers
        '''

    def process_rsync_transfer_with_proxy(self):
        # Execute command proxied_rsync.sh located in the same folder as this python script
        ctx.logger.info('Processing rsync data transfer from source {} to target {}'.format(
            self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
        ))

        try:
            current_dir = os.path.dirname(os.path.realpath(__file__))
            script_path = current_dir + "/proxied_rsync.sh"

            # Generate script invocation command
            # Source DS
            from_source_type = self.dt_config['fromSource']['type']
            from_source_data_url = None
            if 'FileDataSource' in from_source_type:
                from_source_data_url = self.dt_config['fromSource']['properties']['filepath']
                if from_source_data_url.startswith('~/'):
                    from_source_data_url = from_source_data_url[2:]

            from_source_infra_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']
            from_source_infra_credentials = self.dt_config['fromSource']['properties']['located_at']['credentials']

            # Target DS
            to_target_type = self.dt_config['toTarget']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['toTarget']['properties']['filepath']
                if to_target_data_url.startswith('~/'):
                    to_target_data_url = to_target_data_url[2:]
            to_target_infra_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['toTarget']['properties']['located_at']['credentials']

            source_username = from_source_infra_credentials['username']
            source = source_username + '@' + from_source_infra_endpoint + ':' + from_source_data_url
            target_username = to_target_infra_credentials['username']
            target = target_username + '@' + to_target_infra_endpoint + ':' + to_target_data_url
            source_password = None
            target_password = None
            source_private_key = None
            target_private_key = None

            if "password" in to_target_infra_credentials:
                target_password = to_target_infra_credentials['password']
            elif "key" in to_target_infra_credentials:
                target_key = to_target_infra_credentials['key']
                # Save key in temporary file
                with tempfile.NamedTemporaryFile(delete=False) as key_file:
                    key_file.write(bytes(target_key, 'utf-8'))
                    key_file.flush()
                    target_private_key = key_file.name

            if "password" in from_source_infra_credentials:
                source_password = from_source_infra_credentials['password']
            elif "key" in from_source_infra_credentials:
                source_key = from_source_infra_credentials['key']
                # Save key in temporary file
                with tempfile.NamedTemporaryFile(delete=False) as key_file:
                    key_file.write(bytes(source_key, 'utf-8'))
                    key_file.flush()
                    source_private_key = key_file.name

            if source_private_key and target_private_key:
                cmd = script_path + \
                      ' --source_private_key {source_private_key} --source {source}' \
                      ' --target_private_key {target_private_key} --target {target}'.format(
                          source_private_key=source_private_key, source=source,
                          target_private_key=target_private_key, target=target
                      )
            elif source_private_key and target_password:
                cmd = script_path + \
                      ' --source_private_key {source_private_key} --source {source}' \
                      ' --target_password {target_password} --target {target}'.format(
                          source_private_key=source_private_key, source=source,
                          target_password=target_password, target=target
                      )
            elif source_password and target_private_key:
                cmd = script_path + \
                      ' --source_password {source_password} --source {source}' \
                      ' --target_private_key {target_private_key} --target {target}'.format(
                          source_password=source_password, source=source,
                          target_private_key=target_private_key, target=target
                      )
            elif source_password and target_password:
                cmd = script_path + \
                      ' --source_password {source_password} --source {source}' \
                      ' --target_password {target_password} --target {target}'.format(
                          source_password=source_password, source=source,
                          target_password=target_password, target=target
                      )
            else:
                raise CommandExecutionError(
                    "Error in the configuration of rsync data transfer from source {} to target {}".format(
                        self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
                    ))

            cmd_output = os.popen(cmd)
            cmd_msg = cmd_output.read()
            exit_code = cmd_output.close()

            if exit_code is not None:  # exit code is None is successful
                raise CommandExecutionError(
                    "Failed executing rsync data transfer: exit code " + str(exit_code) + " and msg: " + cmd_msg)
        finally:
            if source_private_key and os.path.exists(source_private_key):
                # Remove key temporary file
                os.remove(source_private_key)
            if target_private_key and os.path.exists(target_private_key):
                # Remove key temporary file
                os.remove(target_private_key)

    '''
    Rsync data transfer executed from source data server
    '''

    def process_rsync_transfer(self):
        ssh_client = None
        ftp_client = None

        try:
            ctx.logger.info('Processing rsync data transfer')
            # Copy source data into target data by invoking rsync command at target data infrastructure Create rsync
            # command (check available credentials for target data infrastructure) If credential include
            # user/password, rsync command is: rsync -ratlz --rsh="/usr/bin/sshpass -p <passwd> ssh -o
            # StrictHostKeyChecking=no -o IdentitiesOnly=yes -l <user>" <source files to copy>  <HPC remote
            # server>:<target folder> If credential include user/key, rsync command is: rsync -ratlz -e "ssh -o
            # IdentitiesOnly=yes -i <key_file>"  <files to copy>  <user>@<HPC remote server>:<target folder> Copy key
            # in temporary file and destroy it (whatsoever) after usage (or failure) Invoke command in target
            # infrastructure

            dt_command = None
            target_key_filepath = None

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
                                username=target_username, password=target_password,
                                target_endpoint=to_target_infra_endpoint, ds_source=from_source_data_url,
                                ds_target=to_target_data_url
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
                    dt_command = 'rsync -ratlz -e "ssh -o IdentitiesOnly=yes -i ~/{key_file}"  {ds_source}  ' \
                                 '{username}@{target_endpoint}:{ds_target}'.format(
                                    username=target_username, key_file=target_key_filepath,
                                    target_endpoint=to_target_infra_endpoint,
                                    ds_source=from_source_data_url, ds_target=to_target_data_url
                                    )

            # Execute data transfer command
            exit_msg, exit_code = ssh_client.execute_shell_command(dt_command, wait_result=True)

            if exit_code != 0:
                raise CommandExecutionError(
                    "Failed executing rsync data transfer: exit code " + str(exit_code) + " and msg: " + exit_msg)

        except Exception as exp:
            raise CommandExecutionError(
                "Failed trying to connect to data source infrastructure: " + str(exp))
        finally:
            ftp_client.close_connection()
            ssh_client.close_connection()
