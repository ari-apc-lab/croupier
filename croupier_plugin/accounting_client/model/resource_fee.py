import enum

from .base import AccountingBase


class Currency(enum.Enum):
    EUR = 0
    GBP = 1


class ResourceFee (AccountingBase):

    value = None
    currency = None
    resource_id = None
    amount = None
    discount = None

    def __init__(self, value, currency, amount, discount=None, resource_id=None, id=None):
        self.id = id
        self.resource_id = resource_id
        self.value = value
        self.currency = currency
        self.amount = amount
        self.discount = discount
