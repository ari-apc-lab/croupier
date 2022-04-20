import re
import subprocess
from subprocess import PIPE
from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.ssh import SshClient
from cloudify import ctx
from cloudify.exceptions import CommandExecutionError
import tempfile
import os
from croupier_plugin.data_management.data_management import saveKeyInTemporaryFile

import shutil

target_private_key = None


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
    def __init__(self, data_transfer_config, logger, workdir):
        super().__init__(data_transfer_config, logger, workdir)

    def process(self):
        use_proxy = False
        if 'internet_access' in self.dt_config['to_target']['located_at']:
            use_proxy = not self.dt_config['to_target']['located_at']['internet_access']
        if use_proxy:
            self.process_http_transfer_with_proxy()
        else:
            self.process_http_transfer()

    def process_http_transfer(self):
        try:
            ctx.logger.info('Processing http data transfer from source {} to target {}'.format(
                self.dt_config['from_source']['name'], self.dt_config['to_target']['name']
            ))
            #  Copy source data into target data by invoking wget command at target data infrastructure
            #  Create wget command
            #  Invoke command in target infrastructure

            # Source DS
            resource = self.dt_config['from_source']['resource']
            endpoint = self.dt_config['from_source']['located_at']['endpoint']
            url = resource if resource.startswith('http') else \
                '{endpoint}/{resource}'.format(endpoint=endpoint[:-1] if endpoint.endswith('/') else endpoint,
                                               resource=resource[1:] if resource.startswith('/') else resource)

            # Target DS
            to_target_type = self.dt_config['to_target']['type']
            to_target_data_url = None
            if 'FileDataSource' in to_target_type:
                to_target_data_url = self.dt_config['to_target']['filepath']

            workdir = self.dt_config['to_target']['located_at']['workdir']
            to_target_infra_credentials = self.dt_config['to_target']['located_at']['credentials']
            target_is_file = isFile(to_target_data_url)

            # Specifying target to copy using wget
            curl_command, get_command = self.create_http_get_commands(target_is_file, to_target_data_url, url)

            # Execute data transfer command
            ssh_client = SshClient(to_target_infra_credentials)
            exit_msg, exit_code = ssh_client.execute_shell_command(get_command, workdir=workdir, wait_result=True)
            if exit_code != 0:
                error_msg = 'Could not download using wget, trying with curl (exit code: {0}, error:{1})\n'.format(
                    str(exit_code), exit_msg)
                ctx.logger.warning(error_msg)
                exit_msg, exit_code = ssh_client.execute_shell_command(curl_command, workdir=workdir, wait_result=True)

                if exit_code != 0:
                    error_msg = 'Could not download using curl (exit code: {0}, error:{1})\n'.format(
                        str(exit_code), exit_msg)
                    raise CommandExecutionError(error_msg)
                else:
                    ctx.logger.info("Data downloaded successfully with curl")
            else:
                ctx.logger.info("Data downloaded successfully with wget")
        except Exception as exp:
            ctx.logger.error("There was a problem executing the data transfer: " + str(exp))
            raise
        finally:
            if 'ssh_client' in locals():
                ssh_client.close_connection()

    def create_http_get_command_template(self, from_source_data_url, from_source_infra_endpoint):
        # Support transfer data from GitHub
        dt_command_template = 'cd {temp_dir} & '
        if "github.com" in from_source_infra_endpoint:
            if 'tree' in from_source_infra_endpoint:
                pattern = None
                replacement = None
                if 'main' in from_source_infra_endpoint:
                    pattern = "tree/main"
                    replacement = "trunk"
                else:
                    pattern = "tree"
                    replacement = "branches"
                from_source_infra_endpoint = re.sub("tree", "branches", from_source_infra_endpoint)
            if 'tree' in from_source_data_url:
                pattern = None
                replacement = None
                if 'main' in from_source_data_url:
                    pattern = "tree/main"
                    replacement = "trunk"
                else:
                    pattern = "tree"
                    replacement = "branches"
                from_source_data_url = re.sub("tree", "branches", from_source_data_url)
            dt_command_template += 'svn export {source_endpoint}/{resource}'
        else:
            dt_command_template += 'wget {source_endpoint}/{resource}'
        source_credentials = self.dt_config['from_source']['located_at']['credentials']
        if 'user' in source_credentials and 'password' in source_credentials and \
                source_credentials['user'] and source_credentials['password']:
            dt_command_template += ' --user {0} --password {1}'.format(
                source_credentials['user'], source_credentials['password'])
        elif 'auth-header' in source_credentials and source_credentials['auth-header']:
            auth_header_label = ' --header \'' + source_credentials['auth-header-label'] + ': '
            dt_command_template += auth_header_label + source_credentials['api-token'] + '\''
        return dt_command_template, from_source_data_url, from_source_infra_endpoint

    def create_http_get_commands(self, target_is_file, to_target_data_url, url):
        #  Support transfer data from GitHub
        curl_command = None
        get_command = None
        if "github.com" in url:
            pattern = None
            replacement = None
            if 'tree' in url:
                if 'main' in url:
                    pattern = "tree/main"
                    replacement = "trunk"
                else:
                    pattern = "tree"
                    replacement = "branches"
            url = re.sub(pattern, replacement, url)
            to_target = '/'.join(to_target_data_url.split('/')[:-2])
            get_command = 'cd {ds_target}; svn export {url}'.\
                format(url=url, ds_target=to_target)
        else:
            if to_target_data_url.startswith('~/'):
                to_target_data_url = to_target_data_url[2:]
            if target_is_file:
                get_command = 'wget {url} -O {ds_target}'.format(url=url, ds_target=to_target_data_url)
                curl_command = 'curl {url} -o {ds_target}'.format(url=url, ds_target=to_target_data_url)
            else:
                get_command = 'wget {url} -P {ds_target}'.format(url=url, ds_target=to_target_data_url)
                curl_command = 'cd {ds_target} & curl -O {url}'.format(url=url, ds_target=to_target_data_url)
            source_credentials = self.dt_config['from_source']['located_at']['credentials']
            if 'user' in source_credentials and 'password' in source_credentials and \
                    source_credentials['user'] and source_credentials['password']:
                user = source_credentials['user']
                password = source_credentials['password']
                get_command += ' --user {0} --password {1}'.format(user, password)
                curl_command += ' -u {0}:{1}'.format(user, password)
            elif 'auth-header' in source_credentials and source_credentials['auth-header']:
                auth_header = ' --header \'' + source_credentials['auth-header-label'] + ': ' + source_credentials[
                    'auth-header'] + '\''
                get_command += auth_header
                curl_command += auth_header
        return curl_command, get_command

    def process_http_transfer_with_proxy(self):
        temporary_dir = None
        try:
            ctx.logger.info('Processing http data transfer proxied by Croupier from source {} to target {}'.format(
                self.dt_config['from_source']['name'], self.dt_config['to_target']['name']
            ))

            # Copy source data into croupier temporary folder using wget
            # Source DS
            from_source_data_url = self.dt_config['from_source']['resource']
            from_source_infra_endpoint = self.dt_config['from_source']['located_at']['endpoint']

            dt_command, temporary_dir = self.create_http_get_command_for_proxy(from_source_data_url,
                                                                               from_source_infra_endpoint,
                                                                               temporary_dir)

            # Execute data transfer command
            ctx.logger.info('http(wget) data transfer: executing command: {}'.format(dt_command))
            process = subprocess.run(dt_command, stdout=PIPE, stderr=PIPE, shell=True)
            if process.returncode != 0:
                raise CommandExecutionError(
                    "Failed executing http(wget) data transfer: exit code {code}, stdout: {stdout}, stderr: {stderr}"
                    .format(code=str(process.returncode), stdout=str(process.stdout), stderr=str(process.stderr)))

            # Transfer source data into target using rsync
            # Target DS

            if directoryIsNotEmpty(temporary_dir):
                to_target_type = self.dt_config['to_target']['type']
                to_target_data_url = None
                if 'FileDataSource' in to_target_type:
                    to_target_data_url = self.dt_config['to_target']['filepath']
                    if to_target_data_url.startswith('~/'):
                        to_target_data_url = to_target_data_url[2:]
                to_target_infra_endpoint = self.dt_config['to_target']['located_at']['endpoint']
                to_target_infra_credentials = self.dt_config['to_target']['located_at']['credentials']

                target_username = to_target_infra_credentials['user']
                target_password = None

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
                elif "private_key" in to_target_infra_credentials:
                    target_key = to_target_infra_credentials['private_key']
                    # Save key in temporary file
                    target_private_key = saveKeyInTemporaryFile(target_key)

                if target_private_key:
                    dt_command = 'rsync -ratlz {rsync_options} -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i {key_file}" ' \
                                 '{ds_source} {username}@{target_endpoint}:{ds_target}'.format(
                                    username=target_username, key_file=target_private_key,
                                    target_endpoint=to_target_infra_endpoint,
                                    ds_source=ds_source, ds_target=ds_target, rsync_options=rsync_options)
                elif target_password:
                    dt_command = 'rsync -ratlz --rsh="/usr/bin/sshpass -p {password} ssh -o StrictHostKeyChecking=no' \
                                 ' -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -l {username}" {ds_source}  {target_endpoint}:{ds_target}'.\
                                    format(username=target_username, password=target_password,
                                           target_endpoint=to_target_infra_endpoint, ds_source=ds_source,
                                           ds_target=ds_target)
                else:
                    raise CommandExecutionError(
                        "Error in the configuration of rsync data transfer from source {} to target {}".format(
                            self.dt_config['fromSource']['id'], self.dt_config['toTarget']['id']
                        ))

                ctx.logger.info('http(rsync) data transfer: executing command: {}'.format(dt_command))
                process = subprocess.run(dt_command, stdout=PIPE, stderr=PIPE, shell=True)
                if process.returncode != 0:
                    raise CommandExecutionError(
                        "Failed executing http(rsync) data transfer: exit code {code}, stdout: {stdout}, stderr: {stderr}"
                        .format(code=str(process.returncode), stdout=str(process.stdout), stderr=str(process.stderr)))
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

    def create_http_get_command_for_proxy(self, from_source_data_url, from_source_infra_endpoint, temporary_dir):
        dt_command_template, from_source_data_url, from_source_infra_endpoint, temporary_dir, temp_dir = \
            self.create_http_get_command_template_for_proxy(from_source_data_url, from_source_infra_endpoint)

        dt_command = dt_command_template.format(
            source_endpoint=from_source_infra_endpoint[:-1] if from_source_infra_endpoint.endswith('/')
            else from_source_infra_endpoint,
            resource=from_source_data_url[1:] if from_source_data_url.startswith('/')
            else from_source_data_url,
            temp_dir=temporary_dir
        )
        return dt_command, temp_dir

    def create_http_get_command_template_for_proxy(self, from_source_data_url, from_source_infra_endpoint):
        temporary_dir = tempfile.mkdtemp()
        temp_dir = temporary_dir
        source_credentials = self.dt_config['from_source']['located_at']['credentials']
        dt_command_template = 'cd {temp_dir}; '
        # Support transfer data from GitHub
        if "github.com" in from_source_infra_endpoint:  # get command based on svn for github
            if 'tree' in from_source_infra_endpoint:
                if 'main' in from_source_infra_endpoint:
                    pattern = "tree/main"
                    replacement = "trunk"
                else:
                    pattern = "tree"
                    replacement = "branches"
                from_source_infra_endpoint = re.sub("tree", "branches", from_source_infra_endpoint)
            if 'tree' in from_source_data_url:
                if 'main' in from_source_data_url:
                    pattern = "tree/main"
                    replacement = "trunk"
                else:
                    pattern = "tree"
                    replacement = "branches"
            from_source_data_url = re.sub(pattern, replacement, from_source_data_url)
            dt_command_template += 'svn export '
            if 'user' in source_credentials and 'password' in source_credentials:
                dt_command_template += '--username {username} --password {password} --non-interactive '.format(
                    username=source_credentials['user'], password=source_credentials['password']
                )
            if 'https://' not in from_source_infra_endpoint:
                dt_command_template += 'https://'
            dt_command_template += '{source_endpoint}/{resource}'
            if not isFile(from_source_data_url):  # point to downloaded folder
                temp_dir += '/' + from_source_data_url.split('/')[-1] + '/'
        else:  # get command based on wget for other sources
            dt_command_template += 'wget {source_endpoint}/{resource}'
            if 'user' in source_credentials and 'password' in source_credentials and \
                    source_credentials['user'] and source_credentials['password']:
                dt_command_template += ' --user {0} --password {1}'.format(
                    source_credentials['user'], source_credentials['password'])
            elif 'auth-header' in source_credentials and source_credentials['auth-header']:
                auth_header_label = ' --header \'' + source_credentials['auth-header-label'] + ': '
                dt_command_template += auth_header_label + source_credentials['api-token'] + '\''

        return dt_command_template, from_source_data_url, from_source_infra_endpoint, temporary_dir, temp_dir
