import tempfile


def isDataManagementNode(node):
    return ('croupier.nodes.DataAccessInfrastructure' in node.type_hierarchy or
            'croupier.nodes.DataTransfer' in node.type_hierarchy or
            'croupier.nodes.DataSource' in node.type_hierarchy)


def isDataManagementRelationship(relationship):
    return isDataManagementNode(relationship.target_node)


def getDataTransferInstances(global_dt_instances, global_data_workspaces, direction, job):
    dt_instances = {}
    filterWorkspaces(global_dt_instances, global_data_workspaces)  # Only first invocation makes the work
    for rel in job.relationships:
        if rel.type == direction:

            dt_instances[rel.target.instance.id] = global_dt_instances[rel.target.instance.id]
            for instance in dt_instances[rel.target.instance.id]:
                from_credentials = instance.get("from_source", {}).get("located_at", {}).get("credentials")
                if from_credentials:
                    filterOutEmptyValueEntries(from_credentials)
                to_credentials = instance.get("to_target", {}).get("located_at", {}).get("credentials")
                if to_credentials:
                    filterOutEmptyValueEntries(to_credentials)
                continue

    return dt_instances


# TODO Improve this approach for data management based on global dictionaries.
def filterWorkspaces(global_dt_instances, global_data_workspaces):
    #  Replace {workspace} occurrences with those for task where data has to be sent
    for data_object in global_data_workspaces:
        workspace = global_data_workspaces[data_object]
        for key in global_dt_instances:
            for dt_instance in global_dt_instances[key]:
                if dt_instance["from_source"]["name"] in data_object:
                    if "filepath" in dt_instance["from_source"]:
                        if '${workdir}' in dt_instance["from_source"]["filepath"]:
                            dt_instance["from_source"]["filepath"] = \
                                dt_instance["from_source"]["filepath"].replace('${workdir}', workspace)
                if dt_instance["to_target"]["name"] in data_object:
                    if "filepath" in dt_instance["to_target"]:
                        if '${workdir}' in dt_instance["to_target"]["filepath"]:
                            dt_instance["to_target"]["filepath"] = \
                                dt_instance["to_target"]["filepath"].replace('${workdir}', workspace)


def filterOutEmptyValueEntries(dictionary):
    # filter out empty-value entries
    for key in list(dictionary):
        if isinstance(dictionary[key], str) and len(dictionary[key]) == 0:
            del dictionary[key]


def processDataTransfer(global_dt_instances, global_data_workspaces, job, logger, direction, workdir):
    # For each data transfer object
    # execute data_transfer
    # TODO parallel processing of data transfer
    dt_instances = getDataTransferInstances(global_dt_instances, global_data_workspaces, direction, job)
    for data_instance_id in dt_instances:
        for dt_instance in dt_instances[data_instance_id]:
            dt = DataTransfer.factory(dt_instance, logger, workdir)
            if not dt.dt_config["done"]:
                dt.process()


# helper functions
def saveKeyInTemporaryFile(key):
    with tempfile.NamedTemporaryFile(delete=False) as key_file:
        bytea = bytearray(bytes(key, 'utf-8'))
        if bytea[-1] != 10:  # Add final newline character
            bytea.append(10)
        key_file.write(bytes(bytea))
        key_file.flush()
        return key_file.name


class DataTransfer:
    def __init__(self, data_transfer_config, logger, workdir=None):
        self.dt_config = data_transfer_config
        self.logger = logger
        self.workdir = workdir
        # Based on data transfer type, use the Factory to create an specialized DataTransfer instance

    @staticmethod
    def factory(dt_config, logger, workdir=None):
        if dt_config['transfer_protocol'].upper() == "RSYNC":
            from croupier_plugin.data_management.rsync_dt import RSyncDataTransfer
            return RSyncDataTransfer(dt_config, logger, workdir)
        elif dt_config['transfer_protocol'].upper() == "HTTP":
            from croupier_plugin.data_management.http_dt import HttpDataTransfer
            return HttpDataTransfer(dt_config, logger, workdir)
        elif dt_config['transfer_protocol'].upper() == "GRIDFTP":
            from croupier_plugin.data_management.gridftp_dt import GridFTPDataTransfer
            return GridFTPDataTransfer(dt_config, logger, workdir)
        elif dt_config['transfer_protocol'].upper() == "CKANAPI":
            from croupier_plugin.data_management.ckan_api import CKANAPIDataTransfer
            return CKANAPIDataTransfer(dt_config, logger)
        else:
            return DataTransfer(dt_config, logger)

    def process(self):
        raise NotImplementedError("'process' not implemented.")
