def isDataManagementNode(node):
    return ('croupier.nodes.DataAccessInfrastructure' in node.type_hierarchy or
            'croupier.nodes.DataTransfer' in node.type_hierarchy or
            'croupier.nodes.DataSource' in node.type_hierarchy)


def isDataManagementRelationship(relationship):
    return isDataManagementNode(relationship.target_node)


def getDataTransferInstances(direction, job):
    dt_instances = []
    for rel in job.relationships:
        if rel.type == direction:
            if 'dt_instances' in rel.target.instance.runtime_properties:
                dt_instances = rel.target.instance.runtime_properties['dt_instances']
                for instance in dt_instances:
                    from_credentials = instance.get("from_source", {}).get("located_at", {}).get("credentials")
                    if from_credentials:
                        filterOutEmptyValueEntries(from_credentials)
                    to_credentials = instance.get("to_target", {}).get("located_at", {}).get("credentials")
                    if to_credentials:
                        filterOutEmptyValueEntries(to_credentials)
                break
    return dt_instances


def filterOutEmptyValueEntries(dictionary):
    # filter out empty-value entries
    for key in list(dictionary):
        if isinstance(dictionary[key], str) and len(dictionary[key]) == 0:
            del dictionary[key]


def processDataTransfer(job, logger, direction):
    # For each data transfer object
    # execute data_transfer
    # TODO parallel processing of data transfer
    dt_instances = getDataTransferInstances(direction, job)
    for dt_config in dt_instances:
        dt = DataTransfer.factory(dt_config, logger)
        dt.process()


class DataTransfer:
    def __init__(self, data_transfer_config, logger):
        self.dt_config = data_transfer_config
        self.logger = logger
        # Based on data transfer type, use the Factory to create an specialized DataTransfer instance

    @staticmethod
    def factory(dt_config, logger):
        if dt_config['transfer_protocol'].upper() == "RSYNC":
            from croupier_plugin.data_management.rsync_dt import RSyncDataTransfer
            return RSyncDataTransfer(dt_config, logger)
        elif dt_config['transfer_protocol'].upper() == "HTTP":
            from croupier_plugin.data_management.http_dt import HttpDataTransfer
            return HttpDataTransfer(dt_config, logger)
        elif dt_config['transfer_protocol'].upper() == "GRIDFTP":
            from croupier_plugin.data_management.gridftp_dt import GridFTPDataTransfer
            return GridFTPDataTransfer(dt_config, logger)
        elif dt_config['transfer_protocol'].upper() == "CKANAPI":
            from croupier_plugin.data_management.ckan_api import CKANAPIDataTransfer
            return CKANAPIDataTransfer(dt_config, logger)
        elif dt_config['transfer_protocol'].upper() == "SCP":
            from croupier_plugin.data_management.ckan_scp import CKANSCPDataTransfer
            return CKANSCPDataTransfer(dt_config, logger)
        else:
            return DataTransfer(dt_config, logger)

    def process(self):
        raise NotImplementedError("'process' not implemented.")
