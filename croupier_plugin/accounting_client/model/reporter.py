from __future__ import absolute_import
import enum

from .base import AccountingBase


class ReporterType(enum.Enum):
    Orchestrator = 0
    DataProvider = 1
    Prometheus = 2


class Reporter (AccountingBase):

    name = None
    ip = None
    type = None

    def __init__(self, name, ip, type, id=None):
        self.id = id
        self.name = name
        self.ip = ip
        self.type = type
