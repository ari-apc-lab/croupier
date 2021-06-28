from __future__ import absolute_import
import enum

from .base import AccountingBase


class DiscountUnit(enum.Enum):
    Percentage = 0
    Absolute = 1


class Discount (AccountingBase):
    value = None
    unit = None
    fee_id = None

    def __init__(self, value, unit, fee_id=None, id=None):
        self.id = id
        self.fee_id = fee_id
        self.value = value
        self.unit = unit
