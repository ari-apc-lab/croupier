from croupier_plugin.data_management.data_management import DataTransfer, ssh_credentials
from croupier_plugin.ssh import SshClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError
import tempfile
import os
import shutil


def thereIsOnlyOneFileInDirectory(path):
    return len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))]) == 1


def getOnlyFileInPath(path):
    if thereIsOnlyOneFileInDirectory(path):
        return [name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))][0]
    else:
        return None


def directoryIsNotEmpty(path):
    return len([name for name in os.listdir(path)]) > 0


def isFile(path):
    import re
    pattern = '^.+\.(.*)$'
    res = False
    if re.match(pattern, path):
        res = True
    return res


class HttpDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config):
        super().__init__(data_transfer_config)

    def process(self):
        use_proxy = False
        if 'internet_access' in self.dt_config['toTarget']['properties']['located_at']:
            use_proxy = self.dt_config['toTarget']['properties']['located_at']['internet_access']
        if use_proxy:
            self.process_http_transfer_with_proxy()
        else:
            self.process_http_transfer()

    def process_http_transfer(self):
        ssh_client = None

        try:
            ctx.logger.info('Processing http data transfer from source {} to target {}'.format(
                self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
            ))
            #  Copy source data into target data by invoking wget command at target data infrastructure
            #  Create wget command
            #  Invoke command in target infrastructure

            # Source DS
            from_source_type = self.dt_config['fromSource']['type']
            from_source_data_url = None
            if 'WebDataSource' in from_source_type:
                from_source_data_url = self.dt_config['fromSource']['properties']['resource']
            from_source_infra_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']

            # Target DS
            to_target_type = self.dt_config['toTarget']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['toTarget']['properties']['filepath']
                if to_target_data_url.startswith('~/'):
                    to_target_data_url = to_target_data_url[2:]
            to_target_infra_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
            to_target_infra_credentials = self.dt_config['toTarget']['properties']['located_at']['credentials']

            target_is_file = isFile(to_target_data_url)

            # Specifying target to copy using wget
            dt_command_template = None
            if target_is_file:
                dt_command_template = 'wget {source_endpoint}/{resource} -O {ds_target}'
            else:
                dt_command_template = 'wget {source_endpoint}/{resource} -P {ds_target}'

            dt_command = dt_command_template.format(
                source_endpoint=from_source_infra_endpoint[:-1] if from_source_infra_endpoint.endswith('/')
                else from_source_infra_endpoint,
                resource=from_source_data_url[1:] if from_source_data_url.startswith('/')
                else from_source_data_url, ds_target=to_target_data_url
            )

            credentials = ssh_credentials(to_target_infra_endpoint, to_target_infra_credentials)
            ssh_client = SshClient(credentials)

            # TODO support credentials in wget if given

            # Execute data transfer command
            exit_msg, exit_code = ssh_client.execute_shell_command(dt_command, wait_result=True)

            if exit_code != 0:
                raise CommandExecutionError("Failed executing data transfer: exit code " + str(exit_code))

        except Exception as exp:
            raise CommandExecutionError(
                "Failed trying to connect to data source infrastructure: " + str(exp))
        finally:
            ssh_client.close_connection()

    def process_http_transfer_with_proxy(self):
        temporary_dir = None
        try:
            ctx.logger.info('Processing http data transfer proxied by Croupier from source {} to target {}'.format(
                self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
            ))

            # Copy source data into croupier temporary folder using wget
            # Source DS
            from_source_type = self.dt_config['fromSource']['type']
            from_source_data_url = None
            if 'WebDataSource' in from_source_type:
                from_source_data_url = self.dt_config['fromSource']['properties']['resource']
            from_source_infra_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']

            # TODO support credentials in wget if given
            temporary_dir = tempfile.mkdtemp()
            dt_command = 'cd {temp_dir}; wget {source_endpoint}/{resource}'.format(
                source_endpoint=from_source_infra_endpoint[:-1] if from_source_infra_endpoint.endswith('/')
                else from_source_infra_endpoint,
                resource=from_source_data_url[1:] if from_source_data_url.startswith('/')
                else from_source_data_url,
                temp_dir=temporary_dir
            )

            # Execute data transfer command
            cmd_output = os.popen(dt_command)
            cmd_msg = cmd_output.read()
            exit_code = cmd_output.close()

            if exit_code is not None:  # exit code is None is successful
                raise CommandExecutionError(
                    "Failed executing rsync data transfer: exit code " + str(exit_code) + " and msg: " + cmd_msg)

            # Transfer source data into target using rsync
            # Target DS

            if directoryIsNotEmpty(temporary_dir):
                to_target_type = self.dt_config['toTarget']['type']
                to_target_data_url = None
                if 'FileDataSource' in to_target_type:
                    to_target_data_url = self.dt_config['toTarget']['properties']['filepath']
                    if to_target_data_url.startswith('~/'):
                        to_target_data_url = to_target_data_url[2:]
                to_target_infra_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
                to_target_infra_credentials = self.dt_config['toTarget']['properties']['located_at']['credentials']

                target_username = to_target_infra_credentials['username']
                target_password = None
                target_private_key = None

                source_is_file = thereIsOnlyOneFileInDirectory(temporary_dir)
                target_is_file = isFile(to_target_data_url)

                # Specifying source and target to copy using rsync
                # If both source and target are pointing to directories source_dir is copied in target_dir
                # If both source and target are pointing to files, source_file is copied in target_file
                # If source points to a file and target to a dir, source_file is copied in target_dir
                # If source points to a dir, and target to a file, target_file is interpreted as a dir
                rsync_options = ''
                if not source_is_file:  # dir -> dir
                    ds_source = temporary_dir
                    ds_target = to_target_data_url
                else:  # file -> file/dir
                    if source_is_file and target_is_file:  # support file -> file copy with rsync
                        rsync_options = '--no-R --no-implied-dirs'
                    ds_source = temporary_dir + '/' + getOnlyFileInPath(temporary_dir)
                    ds_target = to_target_data_url

                if "password" in to_target_infra_credentials:
                    target_password = to_target_infra_credentials['password']
                elif "key" in to_target_infra_credentials:
                    target_key = to_target_infra_credentials['key']
                    # Save key in temporary file
                    with tempfile.NamedTemporaryFile(delete=False) as key_file:
                        key_file.write(bytes(target_key, 'utf-8'))
                        key_file.flush()
                        target_private_key = key_file.name

                if target_private_key:
                    dt_command = 'rsync -ratlz {rsync_options} -e "ssh -o IdentitiesOnly=yes -i {key_file}" ' \
                                 '{ds_source} {username}@{target_endpoint}:{ds_target}'.format(
                                    username=target_username, key_file=target_private_key,
                                    target_endpoint=to_target_infra_endpoint,
                                    ds_source=ds_source, ds_target=ds_target, rsync_options=rsync_options)
                elif target_password:
                    dt_command = 'rsync -ratlz --rsh="/usr/bin/sshpass -p {password} ssh -o StrictHostKeyChecking=no' \
                                 ' -o IdentitiesOnly=yes -l {username}" {ds_source}  {target_endpoint}:{ds_target}'.\
                                    format(username=target_username, password=target_password,
                                           target_endpoint=to_target_infra_endpoint, ds_source=ds_source,
                                           ds_target=ds_target)
                else:
                    raise CommandExecutionError(
                        "Error in the configuration of rsync data transfer from source {} to target {}".format(
                            self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
                        ))

                cmd_output = os.popen(dt_command)
                cmd_msg = cmd_output.read()
                exit_code = cmd_output.close()

                if exit_code is not None:  # exit code is None is successful
                    raise CommandExecutionError(
                        "Failed executing rsync data transfer: exit code " + str(exit_code) + " and msg: " + cmd_msg)
            else:
                ctx.logger.warn('HTTP DT: Not transferring data from empty temporary folder')

        except Exception as exp:
            raise CommandExecutionError(
                "Failed trying to connect to data source infrastructure: " + str(exp))
        finally:
            if target_private_key and os.path.exists(target_private_key):
                # Remove key temporary file
                os.remove(target_private_key)
            if temporary_dir and os.path.exists(temporary_dir):
                shutil.rmtree(temporary_dir)
