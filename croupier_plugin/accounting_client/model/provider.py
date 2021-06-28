from __future__ import absolute_import
from .base import AccountingBase


class Provider (AccountingBase):

    name = None
    infrastructures = []

    def __init__(self, name, infrastructures=[], id=None):
        self.id = id
        self.name = name
        self.infrastructures = infrastructures
