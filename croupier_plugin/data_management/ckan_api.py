from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.ssh import SshClient
from ckanapi import RemoteCKAN


class CKANAPIDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config, logger):
        super().__init__(data_transfer_config, logger)

        self.from_infra = data_transfer_config['from_source']['located_at']
        self.to_infra = data_transfer_config['to_target']['located_at']

        if 'CKAN_dataset' in  self.from_infra['type_hierarchy']:
            self.direction = 'download'
            self.ckan_dataset = self.from_infra
        elif 'CKAN_dataset' in self.to_infra['type_hierarchy']:
            self.direction = 'upload'
            self.ckan_dataset = self.to_infra
        else:
            logger.error('CKANAPI Data Transfer must have a "CKAN_dataset" as one of its endpoints')
            raise Exception

        self.dataset_info = self.ckan_dataset['properties']['dataset_info']
        self.endpoint = self.ckan_dataset['endpoint']
        self.apikey = self.ckan_dataset['credentials']['auth-header']

        if not self.dataset['name']:
            self._find_dataset()

    def process(self):
        if self.direction == 'download':
            return self._download_data()
        else:
            return self._upload_data()

    def _find_dataset(self):


    def _download_data(self):


    def _upload_data(self):