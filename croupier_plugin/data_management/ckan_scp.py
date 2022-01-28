from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.ssh import SshClient
from ckanapi import RemoteCKAN, ServerIncompatibleError, NotAuthorized, ValidationError


class CKANAPIDataTransfer(DataTransfer):
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
        self.apikey = self.ckan_dataset['credentials']['auth-header']
        self.api = RemoteCKAN(self.endpoint, apikey=self.apikey)
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
        return False

    def _upload_data(self):
        return False

    def _get_resource(self):
        return False

    def _find_dataset(self):
        return False

    def _create_dataset(self):
		return False

    def _resource_exists(self):
        if self._get_resource():
            return True
        return False
