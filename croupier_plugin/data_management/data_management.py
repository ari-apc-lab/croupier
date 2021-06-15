from cloudify import ctx


def isInputRelationship(relationship):
    return 'input' == relationship._relationship['type']


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


def isDataSourceNode(node):
    return 'croupier.nodes.DataSource' in node.type_hierarchy


def isJobNode(node):
    return 'croupier.nodes.Job' in node.type_hierarchy


def isDataManagementRelationship(relationship):
    return ('input' == relationship._relationship['type'] or
            'output' == relationship._relationship['type'])


def findDataTransferInstancesForSource(data_source, nodes):
    #  find data transfer object in nodes, such as DT|from_source == DS node
    dt_instances = []
    for node in nodes:
        if isDataTransferNode(node):
            for relationship in node.relationships:
                if isFromSourceRelationship(relationship):
                    if data_source.id == relationship.target_node.id:
                        dt_instances.append(node)
    return dt_instances


def findDataTransferInstancesForTarget(data_source, nodes):
    #  find data transfer object in nodes, such as DT|to_target == DS node
    dt_instances = []
    for node in nodes:
        if isDataTransferNode(node):
            for relationship in node.relationships:
                if isToTargetRelationship(relationship):
                    if data_source.id == relationship.target_node.id:
                        dt_instances.append(node)
    return dt_instances


def findDataSourceById(input_id):
    for node in ctx.nodes:
        if isDataSourceNode(node):
            if node.id == input_id:
                return node
    return None


def removeDataTransferInstancesConnectedToJob(job_node, nodes, root_nodes):
    for node in nodes:
        if isDataTransferNode(node):
            dt = node
            if isDTFromSourceInJobOutputs(dt, job_node):
                to_target_rel = getToTargetRelationship(dt)
                input_id = to_target_rel.target_node.id
                removeDTFromInputForAllJobs(dt.id, input_id, root_nodes)


def removeDTFromInputForAllJobs(dt_id, input_id, root_nodes):
    jobs = []
    for node in root_nodes:
        findJobsConnectedToInput(input_id, root_nodes, jobs)
    for job in jobs:
        removeDataTransferInJobInput(dt_id, job, input_id)


def findJobsConnectedToInput(input_id, nodes, jobs):
    for node in nodes:
        if node.is_job:
            for _input in node.inputs:
                if _input['id'] == input_id:
                    if node not in jobs:
                        jobs.append(node)
        if node.children:
            findJobsConnectedToInput(input_id, node.children, jobs)
    return jobs


def removeDataTransferInJobInput(dt_id, job, input_id):
    for _input in job.inputs:
        if _input['id'] == input_id:
            if 'dt_instances' in _input:
                for dt in _input['dt_instances']:
                    if dt['id'] == dt_id:
                        _input['dt_instances'].remove(dt)


def isDTFromSourceInJobOutputs(dt, job_node):
    from_source_rel = getFromSourceRelationship(dt)
    for output in job_node.outputs:
        if from_source_rel.target_node.id == output['id']:
            return True
    return False


def getToTargetRelationship(dt):
    for relationship in dt.relationships:
        if isToTargetRelationship(relationship):
            return relationship
    return None


def getFromSourceRelationship(dt):
    for relationship in dt.relationships:
        if isFromSourceRelationship(relationship):
            return relationship
    return None


def getInputRelationships(job):
    inputs = []
    for relationship in job.relationships:
        if isInputRelationship(relationship):
            inputs.append(relationship)
    return inputs


def getOutputRelationships(job):
    outputs = []
    for relationship in job.relationships:
        if isInputRelationship(relationship):
            outputs.append(relationship)
    return outputs


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


def ssh_credentials(host, dm_credentials):
    credentials = {}
    credentials['host'] = host
    credentials['user'] = dm_credentials['username']
    if 'password' in dm_credentials:
        credentials['password'] = dm_credentials['password']
    if 'key' in dm_credentials:
        credentials['private_key'] = dm_credentials['key']
    if 'key_password' in dm_credentials:
        credentials['private_key_password'] = dm_credentials['key_password']

    return credentials


def processDataTransfer(inouts):
    # For each inout in inouts
    # For each data transfer object in inout
    # execute data_transfer
    # TODO parallel processing of data transfer
    for inout in inouts:
        if 'dt_instances' in inout:
            for dt_config in inout['dt_instances']:
                dt = DataTransfer.factory(dt_config)
                dt.process()


class DataTransfer:
    def __init__(self, data_transfer_config):
        self.dt_config = data_transfer_config
        # Based on data transfer type, use the Factory to create an specialized DataTransfer instance

    @staticmethod
    def factory(dt_config):
        if dt_config['transfer_protocol'].upper() == "RSYNC":
            from croupier_plugin.data_management.rsync_dt import RSyncDataTransfer
            return RSyncDataTransfer(dt_config)

    def process(self):
        raise NotImplementedError(
            "'process' not implemented.")
