import enum

from base import AccountingBase


class MeasureUnit(enum.Enum):
    NumberOf = 0
    Mb = 1
    Gb = 2
    Tb = 3
    Mbps = 4
    Gbps = 5
    Hours = 6


class ResourceConsumption (AccountingBase):

    value = None
    unit = None
    record_id = None
    resource_id = None

    def __init__(self, value, unit, resource_id, record_id=None, id=None):
        self.id = id
        self.value = value
        self.unit = unit
        self.record_id = record_id
        self.resource_id = resource_id
