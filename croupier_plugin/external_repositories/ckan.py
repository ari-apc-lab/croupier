'''
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

ckan.py: Ckan specific communication to publish data
'''


from croupier_plugin.external_repositories.external_repository import \
    ExternalRepository


class Ckan(ExternalRepository):

    def __init__(self, publish_item):
        super(Ckan, self).__init__(publish_item)

        data = publish_item['dataset']
        self.entrypoint = data['config']['entrypoint']
        self.api_key = data['config']['key']
        self.dataset = data['dataset']['id']
        self.file_path = publish_item['file_path']
        self.name = publish_item['name']
        self.description = publish_item["description"]

    def _build_publish_call(self, logger):
        # detach call??
        operation = "create"
        # TODO: if resource file exists, operation="update"
        call = "curl -H'Authorization: " + self.api_key + "' " + \
            "'" + self.entrypoint + "/api/action/resource_" + \
            operation + "' " + \
            "--form upload=@" + self.file_path + " " + \
            "--form package_id=" + self.dataset + " " + \
            "--form name=" + self.name + " " + \
            "--form description='" + self.description + "'"
        return call
