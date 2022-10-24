import tempfile


def isDataManagementNode(node):
    return ('croupier.nodes.DataAccessInfrastructure' in node.type_hierarchy or
            'croupier.nodes.DataTransfer' in node.type_hierarchy or
            'croupier.nodes.DataSource' in node.type_hierarchy)


def isDataManagementRelationship(relationship):
    return isDataManagementNode(relationship.target_node)


def getDataTransferInstances(direction, job, dts):
    dict_dt_instances = {}
    for rel in job.relationships:
        if rel.type == direction:
            data_id = rel.target.node.id
            dt_instances = dts[data_id]
            for instance in dt_instances:
                from_credentials = instance.get("from_source", {}).get("located_at", {}).get("credentials")
                from_workdir = instance.get("from_source", {}).get("workdir")
                if from_credentials:
                    filterOutEmptyValueEntries(from_credentials)
                if from_workdir:
                    if "filepath" in instance["from_source"]:
                        if '${workdir}' in instance["from_source"]["filepath"]:
                            instance["from_source"]["filepath"] = \
                                instance["from_source"]["filepath"].replace('${workdir}', from_workdir)

                to_credentials = instance.get("to_target", {}).get("located_at", {}).get("credentials")
                to_workdir = instance.get("to_target", {}).get("workdir")
                if to_credentials:
                    filterOutEmptyValueEntries(to_credentials)
                if to_workdir:
                    if "filepath" in instance["to_target"]:
                        if '${workdir}' in instance["to_target"]["filepath"]:
                            instance["to_target"]["filepath"] = \
                                instance["to_target"]["filepath"].replace('${workdir}', to_workdir)
                # continue
            dict_dt_instances[rel.target.instance.id] = dt_instances
    return dict_dt_instances


def filterOutEmptyValueEntries(dictionary):
    # filter out empty-value entries
    for key in list(dictionary):
        if isinstance(dictionary[key], str) and len(dictionary[key]) == 0:
            del dictionary[key]


def processDataTransfer(job, logger, direction, workdir, dts):
    # For each data transfer object
    # execute data_transfer
    # TODO parallel processing of data transfer
    dt_instances = getDataTransferInstances(direction, job, dts)
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
