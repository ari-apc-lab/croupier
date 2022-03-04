from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.ssh import SshClient, SFtpClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError
import tempfile
import os
from subprocess import Popen, PIPE


class RSyncDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config, logger, workdir):
        super().__init__(data_transfer_config, logger, workdir)

    def process(self):
        use_proxy = False
        rsync_source_to_target = False
        source_internet_access = False
        target_internet_access = False

        if 'internet_access' in self.dt_config['from_source']['located_at']:
            source_internet_access = self.dt_config['from_source']['located_at']['internet_access']
        if 'internet_access' in self.dt_config['to_target']['located_at']:
            target_internet_access = self.dt_config['to_target']['located_at']['internet_access']

        if source_internet_access:
            rsync_source_to_target = True
        elif target_internet_access:
            rsync_source_to_target = False
        else:
            use_proxy = True

        if use_proxy:
            self.process_rsync_transfer_with_proxy()
        else:
            self.process_rsync_transfer(rsync_source_to_target)

    '''
        Rsync data transfer executed from Croupier server
        Requires sshfs command available (install sshfs package)
        Requires ssh key-based access to both source and target data servers
        '''

    def process_rsync_transfer_with_proxy(self):
        # Execute command proxied_rsync.sh located in the same folder as this python script
        ctx.logger.info('Processing rsync data transfer from source {} to target {}'.format(
            self.dt_config['from_source']['name'], self.dt_config['to_target']['name']
        ))

        try:
            current_dir = os.path.dirname(os.path.realpath(__file__))
            script_path = 'sh ' + current_dir + "/proxied_rsync.sh"

            # Generate script invocation command
            # Source DS
            from_source_type = self.dt_config['from_source']['type']
            from_source_data_url = None
            if 'FileDataSource' in from_source_type:
                from_source_data_url = self.dt_config['from_source']['filepath']
                if from_source_data_url.startswith('~/'):
                    from_source_data_url = from_source_data_url[2:]

            if from_source_data_url is not None and '${workdir}' in from_source_data_url:
                workdir = self.workdir
                if workdir.startswith('~') or workdir.startswith('$HOME'):
                    workdir = self.workdir[self.workdir.find('/') + 1:]
                if not from_source_data_url.startswith('${workdir}'):
                    workdir = self.workdir[self.workdir.rfind('/') + 1:]
                from_source_data_url = from_source_data_url.replace('${workdir}', workdir)

            from_source_infra_endpoint = self.dt_config['from_source']['located_at']['endpoint']
            from_source_infra_credentials = self.dt_config['from_source']['located_at']['credentials']

            # Target DS
            to_target_type = self.dt_config['to_target']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['to_target']['filepath']
                if to_target_data_url.startswith('~/'):
                    to_target_data_url = to_target_data_url[2:]

            if to_target_data_url is not None and '${workdir}' in to_target_data_url:
                workdir = self.workdir
                if workdir.startswith('~') or workdir.startswith('$HOME'):
                    workdir = self.workdir[self.workdir.find('/') + 1:]
                if not to_target_data_url.startswith('${workdir}'):
                    workdir = self.workdir[self.workdir.rfind('/') + 1:]
                to_target_data_url = to_target_data_url.replace('${workdir}', workdir)

            to_target_infra_endpoint = self.dt_config['to_target']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['to_target']['located_at']['credentials']

            source_username = from_source_infra_credentials['user']
            source = source_username + '@' + from_source_infra_endpoint + ':' + from_source_data_url
            target_username = to_target_infra_credentials['user']
            target = target_username + '@' + to_target_infra_endpoint + ':' + to_target_data_url
            source_password = None
            target_password = None
            source_private_key = None
            target_private_key = None

            if "password" in to_target_infra_credentials:
                target_password = to_target_infra_credentials['password']
            elif "private_key" in to_target_infra_credentials:
                target_key = to_target_infra_credentials['private_key']
                # Save key in temporary file
                with tempfile.NamedTemporaryFile(delete=False) as key_file:
                    key_file.write(bytes(target_key, 'utf-8'))
                    key_file.flush()
                    target_private_key = key_file.name

            if "password" in from_source_infra_credentials:
                source_password = from_source_infra_credentials['password']
            elif "private_key" in from_source_infra_credentials:
                source_key = from_source_infra_credentials['private_key']
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
                        self.dt_config['from_source']['name'], self.dt_config['to_target']['name']
                    ))

            ctx.logger.info('rsync data transfer: executing command: {}'.format(cmd))
            process = Popen(cmd.split(' '), stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            exit_code = process.returncode
            if exit_code != 0:
                raise CommandExecutionError(
                    "Failed executing rsync data transfer: exit code {code}, stdout: {stdout}, stderr: {stderr}"
                    .format(code=str(exit_code), stdout=str(stdout), stderr=str(stderr)))
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

    def process_rsync_transfer(self, rsync_source_to_target):
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

            # Source DS
            from_source_type = self.dt_config['from_source']['type']
            from_source_data_url = None
            if 'FileDataSource' in from_source_type:
                from_source_data_url = self.dt_config['from_source']['filepath']
            if from_source_data_url is not None and '${workdir}' in from_source_data_url:
                from_source_data_url = from_source_data_url.replace('${workdir}', self.workdir)
            from_source_infra_endpoint = self.dt_config['from_source']['located_at']['endpoint']
            from_source_infra_credentials = self.dt_config['from_source']['located_at']['credentials']

            # Target DS
            to_target_type = self.dt_config['to_target']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['to_target']['filepath']
            if to_target_data_url is not None and '${workdir}' in to_target_data_url:
                to_target_data_url = to_target_data_url.replace('${workdir}', self.workdir)
            to_target_infra_endpoint = self.dt_config['to_target']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['to_target']['located_at']['credentials']

            if rsync_source_to_target:
                credentials = from_source_infra_credentials
            else:
                credentials = to_target_infra_credentials

            ssh_client = SshClient(credentials)
            ftp_client = SFtpClient(credentials)

            if rsync_source_to_target:
                if "user" in to_target_infra_credentials and "password" in to_target_infra_credentials:
                    # NOTE rsync authentication with username/password requires sshpass which it is not installed
                    # some HPC frontends
                    target_username = to_target_infra_credentials['user']
                    target_password = to_target_infra_credentials['password']
                    dt_command = 'rsync -ratlz --rsh="/usr/bin/sshpass -p {password} ssh -o StrictHostKeyChecking=no ' \
                                 '-o IdentitiesOnly=yes -l {username}" {ds_source}  {target_endpoint}:{ds_target}'\
                        .format(
                            username=target_username, password=target_password,
                            target_endpoint=to_target_infra_endpoint, ds_source=from_source_data_url,
                            ds_target=to_target_data_url
                        )
                elif "user" in to_target_infra_credentials and "private_key" in to_target_infra_credentials:
                    target_username = to_target_infra_credentials['user']
                    target_key = to_target_infra_credentials['private_key']
                    # Save key in temporary file
                    with tempfile.NamedTemporaryFile() as key_file:
                        key_file.write(bytes(target_key, 'utf-8'))
                        key_file.flush()
                        key_filepath = key_file.name
                        target_key_filepath = key_file.name.split('/')[-1]
                        # Transfer key_file
                        ftp_client.sendKeyFile(ssh_client, key_filepath, target_key_filepath)
                        dt_command = 'rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i ~/{key_file}" {ds_source} ' \
                                     '{username}@{target_endpoint}:{ds_target}'.format(
                                        username=target_username, key_file=target_key_filepath,
                                        target_endpoint=to_target_infra_endpoint,
                                        ds_source=from_source_data_url, ds_target=to_target_data_url
                                        )
            else:
                if "user" in from_source_infra_credentials and "password" in from_source_infra_credentials:
                    # NOTE rsync authentication with username/password requires sshpass which it is not installed
                    # some HPC frontends

                    source_username = from_source_infra_credentials['user']
                    source_password = from_source_infra_credentials['password']
                    dt_command = 'rsync -ratlz --rsh="/usr/bin/sshpass -p {password} ssh -o StrictHostKeyChecking=no ' \
                                 '-o IdentitiesOnly=yes -l {username}" {source_endpoint}:{ds_source} {ds_target}'\
                        .format(
                            username=source_username, password=source_password,
                            source_endpoint=from_source_infra_endpoint, ds_source=from_source_data_url,
                            ds_target=to_target_data_url
                        )
                elif "username" in from_source_infra_credentials and "private_key" in from_source_infra_credentials:
                    source_username = from_source_infra_credentials['user']
                    source_key = from_source_infra_credentials['private_key']
                    # Save key in temporary file
                    with tempfile.NamedTemporaryFile() as key_file:
                        key_file.write(bytes(source_key, 'utf-8'))
                        key_file.flush()
                        key_filepath = key_file.name
                        source_key_filepath = key_file.name.split('/')[-1]
                        # Transfer key_file
                        ftp_client.sendKeyFile(ssh_client, key_filepath, source_key_filepath)
                        dt_command = 'rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i ~/{key_file}" ' \
                                     '{username}@{source_endpoint}:{ds_source} {ds_target}'.format(
                                        username=source_username, key_file=source_key_filepath,
                                        source_endpoint=from_source_infra_endpoint,
                                        ds_source=from_source_data_url, ds_target=to_target_data_url
                                        )

            # Execute data transfer command
            ctx.logger.info('rsync data transfer: executing command: {}'.format(dt_command))
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
