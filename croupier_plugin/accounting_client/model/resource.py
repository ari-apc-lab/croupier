from __future__ import absolute_import
import enum

from .base import AccountingBase


class ResourceType(enum.Enum):
    CPU = 0
    GPU = 1
    Node = 2
    Storage = 3
    Memory = 4
    Network_Bandwidth = 5
    Data = 6
    Service = 7


class Resource (AccountingBase):

    name = None
    type = None
    fee = None
    infrastructure_id = None

    def __init__(self, name, type, infrastructure_id, fee=None, id=None):
        self.id = id
        self.infrastructure_id = infrastructure_id
        self.name = name
        self.type = type
        self.fee = fee
