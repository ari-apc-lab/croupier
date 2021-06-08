def isOutputRelationship(relationship):
    return 'output' == relationship._relationship['type']


def isFromSourceRelationship(relationship):
    return 'from_source' == relationship._relationship['type']


def isToTargetRelationship(relationship):
    return 'to_target' == relationship._relationship['type']


def isDataManagementNode(node):
    return not ('croupier.nodes.Job' in node.type_hierarchy or
                'croupier.nodes.InfrastructureInterface' in node.type_hierarchy)


def isDataTransferNode(node):
    return 'croupier.nodes.DataTransfer' in node.type_hierarchy


def isDataManagementRelationship(relationship):
    return ('input' == relationship._relationship['type'] or
            'output' == relationship._relationship['type'])


def findDataTransferInstancesForSource(data_source, nodes):
    #  find data transfer object in nodes, such as DT|from-source == DS node
    dt_instances = []
    for node in nodes:
        if isDataTransferNode(node):
            for relationship in node.relationships:
                if isFromSourceRelationship(relationship):
                    if data_source.id == relationship.target_node.id:
                        dt_instances.append(node)
    return dt_instances


def createDataSourceNode(output, dt_instances=None):
    dsNode = {}
    dsNode['id'] = output.id
    dsNode['type'] = output.type
    dsNode['properties'] = output.properties
    data_transfer_instances = []
    if dt_instances:
        for dt_instance in dt_instances:
            data_transfer_instances.append(createDataTransferNode(dt_instance))
    dsNode['dt_instances'] = data_transfer_instances
    return dsNode


def createDataTransferNode(dt_instance):
    dtNode = {}
    dtNode['id'] = dt_instance.id
    dtNode['transfer_protocol'] = dt_instance.properties['transfer_protocol']
    for relationship in dt_instance.relationships:
        if isFromSourceRelationship(relationship):
            dtNode['fromSource'] = createDataSourceNode(relationship.target_node)
        if isToTargetRelationship(relationship):
            dtNode['toTarget'] = createDataSourceNode(relationship.target_node)
    return dtNode


def processDataTransfer(outputs):
    # For each output in outputs
    # For each data transfer object in output
    # execute data_transfer
    # TODO parallel processing of data transfer
    for output in outputs:
        if 'dt_instances' in output:
            for dt_config in output['dt_instances']:
                dt = DataTransfer.factory(dt_config)
                dt.process()


class DataTransfer:
    def __init__(self, data_transfer_config):
        self.dt_config = data_transfer_config
        # Based on data transfer type, use the Factory to create an specialized DataTransfer instance

    @staticmethod
    def factory(dt_config):
        if dt_config['transfer_protocol'].upper() == "RSYNC":
            return RSyncDataTransfer(dt_config)

    def process(self):
        raise NotImplementedError(
            "'process' not implemented.")


class RSyncDataTransfer:
    def __init__(self, data_transfer_config):
        self.dt_config = data_transfer_config

    def process(self):
        # TODO
        raise NotImplementedError(
            "'process' not implemented.")