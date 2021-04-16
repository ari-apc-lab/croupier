from __future__ import absolute_import
import enum

from .base import AccountingBase


class InfrastructureType(enum.Enum):
    Cloud = 0
    HPC = 1
    DataStorage = 2


class Infrastructure (AccountingBase):
    name = None
    server = None
    type = None
    resources = []
    provider_id = None

    def __init__(self, name, server, type, provider_id, resources=[], id=None):
        self.id = id
        self.provider_id = provider_id
        self.name = name
        self.server = server
        self.type = type
        self.resources = resources
