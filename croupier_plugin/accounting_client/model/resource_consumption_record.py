from base import AccountingBase


class ResourceConsumptionRecord (AccountingBase):

    start_transaction = None
    stop_transaction = None
    workflow_id = None
    task_id = None
    workflow_parameters = None
    consumptions = []
    user_id = None
    reporter_id = None

    def __init__(self, start_transaction, stop_transaction, workflow_id,
                 task_id, workflow_parameters, consumptions, user_id, reporter_id, id=None):
        self.id = id
        self.start_transaction = start_transaction
        self.stop_transaction = stop_transaction
        self.workflow_id = workflow_id
        self.task_id = task_id
        self.workflow_parameters = workflow_parameters
        self.consumptions = consumptions
        self.user_id = user_id
        self.reporter_id = reporter_id
