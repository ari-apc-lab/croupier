from __future__ import absolute_import
from .base import AccountingBase


class ResourceAmount (AccountingBase):

    value = None
    unit = None
    fee_id = None

    def __init__(self, value, unit, fee_id=None, id=None):
        self.id = id
        self.fee_id = fee_id
        self.value = value
        self.unit = unit
