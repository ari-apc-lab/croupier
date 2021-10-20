"""
Copyright (c) 2019 Atos Spain SA. All rights reserved.

This file is part of Croupier.

Croupier is free software: you can redistribute it and/or modify it
under the terms of the Apache License, Version 2.0 (the License) License.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT, IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

See README file for full disclaimer information and LICENSE file for full
license information in the project root.

@author: Javier Carnero
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: javier.carnero@atos.net

external_repository.py: Holds the external repository common behaviour
"""

from builtins import object
from croupier_plugin.ssh import SshClient


class ExternalRepository(object):

    def factory(publish_item):
        ptype = publish_item['dataset']['type'].upper()
        if ptype == "CKAN":
            from croupier_plugin.external_repositories.ckan import Ckan
            return Ckan(publish_item)
        else:
            return None
    factory = staticmethod(factory)

    def __init__(self, publish_item):
        self.er_type = publish_item['dataset']['type']

    def publish(self,
                ssh_client,
                logger,
                workdir=None):
        """
        Publish the local file in the external repository

        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @rtype string
        @return False if something went wrong
        """
        if not SshClient.check_ssh_client(ssh_client, logger):
            return False

        call = self._build_publish_call(logger)
        if call is None:
            return False

        return ssh_client.execute_shell_command(
            call,
            workdir=workdir,
            wait_result=False)

    def _build_publish_call(self, logger):
        """
        Creates a script to publish the local file

        @rtype string
        @return string with the publish call. None if an error arise.
        """
        raise NotImplementedError("'_build_publish_call' not implemented.")
