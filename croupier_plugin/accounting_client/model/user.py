from __future__ import absolute_import
from .base import AccountingBase


class User (AccountingBase):

    username = None

    def __init__(self, username, id=None):
        self.id = id
        self.username = username
