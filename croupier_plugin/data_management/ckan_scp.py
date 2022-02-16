from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.ssh import SshClient
from ckanapi import RemoteCKAN, ServerIncompatibleError, NotAuthorized, ValidationError
import os
import uuid


class CKANSCPDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config, logger):
        super().__init__(data_transfer_config, logger)

        self.from_infra = data_transfer_config['from_source']['located_at']
        self.to_infra = data_transfer_config['to_target']['located_at']

        if 'croupier.nodes.CKAN_dataset' in self.from_infra['type_hierarchy']:
            self.direction = 'download'
            self.ckan_dataset = self.from_infra
            self.ckan_resource = data_transfer_config['from_source']['resource']
        elif 'croupier.nodes.CKAN_dataset' in self.to_infra['type_hierarchy']:
            self.direction = 'upload'
            self.ckan_dataset = self.to_infra
            self.ckan_resource = data_transfer_config['to_target']['resource']
        else:
            logger.error('CKANAPI Data Transfer must have a "CKAN_dataset" as one of its endpoints')
            raise Exception

        self.dataset_info = self.ckan_dataset['dataset_info']
        self.endpoint = self.ckan_dataset['endpoint']
        self.apikey = self.ckan_dataset['credentials']['user']
        self.api = RemoteCKAN(self.endpoint, apikey=self.apikey)

        self.scp_username = self.ckan_dataset['credentials']['user']
        self.scp_sshkey = self.ckan_dataset['credentials']['private_key']

        if not self.dataset_info['package_id']:
            self._find_dataset()

        try:
            self.api.action.site_read()
        except ServerIncompatibleError:
            self.logger.error('Could not connect to CKAN server, non valid endpoint')

    def process(self):
        if self.direction == 'download':
            return self._download_data()
        else:
            return self._upload_data()

    def _download_data(self):
        if not self.ckan_resource['url']:
            resource = self._get_resource()
            if not resource:
                self.logger.error("Could not find resource in CKAN")
                raise Exception
            else:
                self.ckan_resource['url'] = resource['url']
        dt_config = {
            'transfer_protocol': 'HTTP',
            'to_target': self.dt_config['to_target'],
            'from_source': {
                'resource': self.ckan_resource['url'],
                'located_at': self.ckan_dataset,
                'name': 'CKAN-' + self.dataset_info['name']
            }
        }
        dt = DataTransfer.factory(dt_config, self.logger)
        dt.process()

    def _upload_data(self):
        if not self.dataset_info['package_id']:
            self._create_dataset()
        ssh_credentials = self.from_infra['credentials']

        filepath = self.dt_config['from_source']['filepath']
        workdir = self.from_infra['workdir']

        fileuuid = uuid.uuid4();
        command = 'echo "' + self.scp_sshkey + '" > .priv_ckan.key; chmod 0600 .priv_ckan.key'
        command += '; scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i .priv_ckan.key ' + filepath + \
                   ' ' + self.scp_username + '@62.3.171.150:~/ckan/' + fileuuid
        command += '; rm .priv_ckan.key'
        action = 'update' if self._resource_exists() else 'create'
        command += '; curl {0}/api/action/resource_{1}'.format(self.endpoint, action)
        command += ' --form name={0}'.format(os.path.basename(filepath))
        command += ' --form url=https://ckan.hidalgo-project.eu:8443/{0}/{1}'.format(self.scp_username, fileuuid)
        command += ' --form package_id={0}'.format(self.dataset_info['package_id'])

        for arg in self.ckan_resource:
            if self.ckan_resource[arg]:
                command += ' --form {0}={1}'.format(arg, self.ckan_resource[arg])

        if self.apikey:
            command += " -H 'Authorization: {0}'".format(self.apikey)
        print(command)
        ssh_client = SshClient(ssh_credentials)
        exit_code, exit_msg = ssh_client.execute_shell_command(command, workdir, wait_result=True)
        if exit_code != 0:
            self.logger.error('There was a problem publishing the results in CKAN ({0}):\n{1}'
                              .format(exit_code, exit_msg))
        else:
            self.logger.info('Data published in CKAN')

    def _get_resource(self):
        if not self.ckan_resource['name']:
            self.logger.error("No name given for resource. Resource search not implemented yet.")
            raise NotImplementedError("CKAN resource search not implemented yet. Must identify it by name.")

        r = self.api.call_action('resource_search', {'query': 'name:' + self.ckan_resource['name']})
        if r['count'] == 0:
            return None
        results = r['results']
        for result in results:
            if result['package_id'] != self.dataset_info['package_id']:
                results.remove(result)

        count = len(results)
        if count == 0:
            return None
        elif count > 1:
            self.logger.error("Found {0} entries in the selected dataset with the given name".format(count))
            raise Exception

        return results[0]

    def _find_dataset(self):
        if not self.dataset_info['name']:
            self.logger.error("No name given for dataset. Dataset search not implemented yet.")
            raise NotImplementedError("CKAN Dataset search not implemented yet. Must identify it by name.")
        search_dict = {
            'fq': 'name:' + self.dataset_info['name'],
            'include_private': True
        }
        try:
            api_search = self.api.call_action('package_search', search_dict)
        except NotAuthorized:
            self.logger.error('Got unauthorized error when trying to search dataset: ' + self.dataset_info['name'])
            raise

        if api_search['count'] > 1:
            self.logger.error('Got more than 1 result for the given CKAN dataset name.')
            raise Exception
        if api_search['count'] == 0:
            self.dataset_info['package_id'] = ''
            return

        self.dataset_info['package_id'] = api_search['results'][0]['id']

    def _create_dataset(self):
        create_dict = {}
        for key in self.dataset_info:
            if not self.dataset_info[key]:
                continue
            create_dict[key] = self.dataset_info[key]
        try:
            r = self.api.call_action('package_create', create_dict)
        except (ValidationError, NotAuthorized) as e:
            self.logger.error('Could not create CKAN dataset:\n{0}'.format(str(e.error_dict)))
            raise Exception

        self.dataset_info['package_id'] = r['id']

    def _resource_exists(self):
        if self._get_resource():
            return True
        return False
