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

@author: Jesus Gorronogoitia
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: jesus.gorronogoitia@atos.net

accounting_client.py: provides API client for Accounting component
"""
from __future__ import print_function
from __future__ import absolute_import
import json
from datetime import datetime
from enum import Enum
import ConfigParser
import os

import requests
from requests import HTTPError

from .model.base import AccountingBase
from .model.user import User
from .model.reporter import Reporter
from .model.provider import Provider
from .model.infrastructure import Infrastructure
from .model.resource import Resource
from .model.resource_fee import ResourceFee
from .model.resource_amount import ResourceAmount
from .model.discount import Discount
from .model.resource_consumption_record import ResourceConsumptionRecord
from .model.resource_consumption import ResourceConsumption

def str_to_bool(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        raise ValueError  # evil ValueError that doesn't tell you what the wrong value was


class AccountingEncoder(json.JSONEncoder):
    def default(self, obj):
        fields = {}
        for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
            data = getattr(obj, field)
            if data is None:
                continue
            elif isinstance(data, list):
                the_list = []
                for item in data:
                    the_list.append(self.default(item))
                fields[field] = the_list
            elif isinstance(data, datetime):
                fields[field] = str(data)
            elif isinstance(data, AccountingBase):
                fields[field] = self.default(data)
            else:
                if isinstance(data, Enum):
                    data = data.name
                try:
                    json.dumps(data)  # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
        # a json-encodable dict
        return fields


class AccountingClient:
    endpoint = "http://0.0.0.0:5000/api/"
    report_to_accounting = False

    def __init__(self, endpoint="http://0.0.0.0:5000/api/"):
        # Configure Accounting endpoint from configuration file
        config = ConfigParser.RawConfigParser()
        config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/../Croupier.cfg'
        print('Reading Accounting configuration from file {file}'.format(
            file=config_file))
        config.read(config_file)
        self.endpoint = endpoint
        try:
            accounting_endpoint = config.get('Accounting', 'endpoint')
            if accounting_endpoint is not None:
                self.endpoint = accounting_endpoint

            report_to_accounting = config.get('Accounting', 'report_to_accounting')
            if report_to_accounting is not None:
                self.report_to_accounting = str_to_bool(report_to_accounting)
        except ConfigParser.NoSectionError:
            pass

    # Users API client
    def get_users(self):
        users_endpoint = self.endpoint + 'users'
        resp = requests.get(users_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + users_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        users = []
        if resp.json() is not None:
            for item in resp.json():
                user = User(**item)
                users.append(user)
        return users

    def get_user(self, users_endpoint):
        resp = requests.get(users_endpoint)
        if resp.status_code != 200:
            raise HTTPError('GET ' + users_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return User(**resp.json())
        else:
            return None

    def get_user_by_id(self, id):
        users_endpoint = self.endpoint + 'users/' + id
        return self.get_user(users_endpoint)

    def get_user_by_name(self, name):
        users_endpoint = self.endpoint + 'users/name/' + name
        return self.get_user(users_endpoint)

    def add_user(self, user):
        users_endpoint = self.endpoint + 'users'
        encoder = AccountingEncoder()
        user_dic = encoder.default(obj=user)
        resp = requests.post(users_endpoint, json=user_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + users_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return User(**resp.json())

    def update_user(self, user):
        users_endpoint = self.endpoint + 'users/' + str(user.id)
        encoder = AccountingEncoder()
        user_dic = encoder.default(obj=user)
        resp = requests.put(users_endpoint, json=user_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + users_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_user(self, user):
        users_endpoint = self.endpoint + 'users/' + str(user.id)
        resp = requests.delete(users_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + users_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Reporters API client
    def get_reporters(self):
        reporters_endpoint = self.endpoint + 'reporters'
        resp = requests.get(reporters_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + reporters_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        reporters = []
        if resp.json() is not None:
            for item in resp.json():
                reporter = Reporter(**item)
                reporters.append(reporter)
        return reporters

    def get_reporter(self, reporters_endpoint):
        resp = requests.get(reporters_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + reporters_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return Reporter(**resp.json())
        else:
            return None

    def get_reporter_by_id(self, id):
        reporters_endpoint = self.endpoint + 'reporters/' + id
        return self.get_reporter(reporters_endpoint)

    def get_reporter_by_name(self, name):
        reporters_endpoint = self.endpoint + 'reporters/name/' + name
        return self.get_reporter(reporters_endpoint)

    def get_reporter_by_type(self, type):
        reporters_endpoint = self.endpoint + 'reporters/type/' + type
        return self.get_reporter(reporters_endpoint)

    def get_reporter_by_ip(self, ip):
        reporters_endpoint = self.endpoint + 'reporters/ip/' + ip
        return self.get_reporter(reporters_endpoint)

    def add_reporter(self, reporter):
        reporters_endpoint = self.endpoint + 'reporters'
        encoder = AccountingEncoder()
        reporter_dic = encoder.default(obj=reporter)
        resp = requests.post(reporters_endpoint, json=reporter_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + reporters_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return Reporter(**resp.json())

    def update_reporter(self, reporter):
        reporters_endpoint = self.endpoint + 'reporters/' + str(reporter.id)
        encoder = AccountingEncoder()
        reporter_dic = encoder.default(obj=reporter)
        resp = requests.put(reporters_endpoint, json=reporter_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + reporters_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_reporter(self, reporter):
        reporters_endpoint = self.endpoint + 'reporters/' + str(reporter.id)
        resp = requests.delete(reporters_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + reporters_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Providers API client
    def get_providers(self):
        providers_endpoint = self.endpoint + 'providers'
        resp = requests.get(providers_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + providers_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        providers = []
        if resp.json() is not None:
            for item in resp.json():
                provider = self.read_provider(item)
                providers.append(provider)
        return providers

    def get_provider(self, providers_endpoint):
        resp = requests.get(providers_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + providers_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return Provider(**resp.json())
        else:
            return None

    def get_provider_by_id(self, id):
        providers_endpoint = self.endpoint + 'providers/' + id
        return self.get_provider(providers_endpoint)

    def get_provider_by_name(self, name):
        providers_endpoint = self.endpoint + 'providers/name/' + name
        return self.get_provider(providers_endpoint)

    def add_provider(self, provider):
        providers_endpoint = self.endpoint + 'providers'
        encoder = AccountingEncoder()
        provider_dic = encoder.default(obj=provider)
        resp = requests.post(providers_endpoint, json=provider_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + providers_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return Provider(**resp.json())

    def update_provider(self, provider):
        providers_endpoint = self.endpoint + 'providers/' + str(provider.id)
        encoder = AccountingEncoder()
        provider_dic = encoder.default(obj=provider)
        resp = requests.put(providers_endpoint, json=provider_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + providers_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_provider(self, provider):
        providers_endpoint = self.endpoint + 'providers/' + str(provider.id)
        resp = requests.delete(providers_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + providers_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Infrastructure API client
    def get_infrastructures(self, provider_id):
        infra_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures'
        resp = requests.get(infra_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + infra_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        infrastructures = []
        if resp.json() is not None:
            for item in resp.json():
                infra = self.read_infrastructure(item)
                infrastructures.append(infra)
        return infrastructures

    def get_infrastructure(self, infra_endpoint):
        resp = requests.get(infra_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + infra_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return Infrastructure(**resp.json())
        else:
            return None

    def get_infrastructure_by_id(self, provider_id, id):
        infra_endpoint = self.endpoint + 'providers' + '/' + str(provider_id) + '/infrastructures/' + id
        return self.get_infrastructure(infra_endpoint)

    def get_infrastructure_by_name(self, provider_id, name):
        infra_endpoint = self.endpoint + 'providers' + '/' + str(provider_id) + '/infrastructures/name/' + name
        return self.get_infrastructure(infra_endpoint)

    def get_infrastructure_by_type(self, provider_id, type):
        infra_endpoint = self.endpoint + 'providers' + '/' + str(provider_id) + '/infrastructures/type/' + type
        return self.get_infrastructure(infra_endpoint)

    def get_infrastructure_of_provider_by_server(self, provider_id, server):
        infra_endpoint = self.endpoint + 'providers' + '/' + str(provider_id) + '/infrastructures/server/' + server
        return self.get_infrastructure(infra_endpoint)

    def get_infrastructure_by_server(self, server):
        infra_endpoint = self.endpoint + '/infrastructures/server/' + server
        return self.get_infrastructure(infra_endpoint)

    def add_infrastructure(self, provider_id, infrastructure):
        infra_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures'
        encoder = AccountingEncoder()
        infra_dic = encoder.default(obj=infrastructure)
        resp = requests.post(infra_endpoint, json=infra_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + infra_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return Infrastructure(**resp.json())

    def update_infrastructure(self, provider_id, infra_id, infrastructure):
        infra_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra_id)
        encoder = AccountingEncoder()
        infra_dic = encoder.default(obj=infrastructure)
        resp = requests.put(infra_endpoint, json=infra_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + infra_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_infrastructure(self, provider_id, infra):
        infra_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra.id)
        resp = requests.delete(infra_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + infra_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Resource API client
    def get_resources(self, provider_id, infra_id):
        resources_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra_id) + '/resources'
        return self._get_resources(resources_endpoint)

    def _get_resources (self, resources_endpoint):
        resp = requests.get(resources_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + resources_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        resources = []
        if resp.json() is not None:
            for item in resp.json():
                resource = self.read_resource(item)
                resources.append(resource)
        return resources

    def _get_resource(self, resources_endpoint):
        resp = requests.get(resources_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + resources_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return self.read_resource(resp.json())
        else:
            return None

    def get_resource_of_provider_by_id(self, provider_id, infra_id, id):
        resources_endpoint = \
            self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra_id) + '/resources/' + id
        return self._get_resource(resources_endpoint)

    def get_resource_by_id(self, infra_id, id):
        resources_endpoint = \
            self.endpoint + '/infrastructures/' + str(infra_id) + '/resources/' + id
        return self._get_resource(resources_endpoint)

    def get_resource_by_name(self, provider_id, infra_id, name):
        resources_endpoint = \
            self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra_id) + '/resources/name/' + name
        return self._get_resource(resources_endpoint)

    def get_resources_by_type(self, provider_id, infra_id, type):
        resources_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' \
                             + str(infra_id) + '/resources/type/' + str(type.name)
        return self._get_resources(resources_endpoint)

    def add_resource(self, provider_id, infra_id, resource):
        resources_endpoint = \
            self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + str(infra_id) + '/resources'
        encoder = AccountingEncoder()
        resource_dic = encoder.default(obj=resource)
        resp = requests.post(resources_endpoint, json=resource_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + resources_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return Resource(**resp.json())

    def update_resource(self, provider_id, infra_id, resource_id, resource):
        resources_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                             str(infra_id) + '/resources/' + str(resource_id)
        encoder = AccountingEncoder()
        resource_dic = encoder.default(obj=resource)
        resp = requests.put(resources_endpoint, json=resource_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + resources_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_resource(self, provider_id, infra_id, resource):
        resources_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                             str(infra_id) + '/resources/' + str(resource.id)
        resp = requests.delete(resources_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + resources_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Resource Fee API client
    def get_fee(self, provider_id, infra_id, resource_id):
        fee_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                       str(infra_id) + '/resources/' + str(resource_id) + '/fee'
        resp = requests.get(fee_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + fee_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return ResourceFee(**resp.json())
        else:
            return None

    def set_fee(self, provider_id, infra_id, resource_id, fee):
        fee_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                       str(infra_id) + '/resources/' + str(resource_id) + '/fee'
        encoder = AccountingEncoder()
        fee_dic = encoder.default(obj=fee)
        resp = requests.post(fee_endpoint, json=fee_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + fee_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return ResourceFee(**resp.json())

    def update_fee(self, provider_id, infra_id, resource_id, fee):
        fee_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                       str(infra_id) + '/resources/' + str(resource_id) + '/fee'
        encoder = AccountingEncoder()
        fee_dic = encoder.default(obj=fee)
        resp = requests.put(fee_endpoint, json=fee_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + fee_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_fee(self, provider_id, infra_id, resource_id):
        fee_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                       str(infra_id) + '/resources/' + str(resource_id) + '/fee'
        resp = requests.delete(fee_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + fee_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Resource discount REST API client
    def get_discount(self, provider_id, infra_id, resource_id):
        discount_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                            str(infra_id) + '/resources/' + str(resource_id) + '/discount'
        resp = requests.get(discount_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + discount_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        if resp.json() is not None:
            return Discount(**resp.json())
        else:
            return None

    def set_discount(self, provider_id, infra_id, resource_id, discount):
        discount_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                            str(infra_id) + '/resources/' + str(resource_id) + '/discount'
        encoder = AccountingEncoder()
        discount_dic = encoder.default(obj=discount)
        resp = requests.post(discount_endpoint, json=discount_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + discount_dic + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return Discount(**resp.json())

    def update_discount(self, provider_id, infra_id, resource_id, discount):
        discount_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                            str(infra_id) + '/resources/' + str(resource_id) + '/discount'
        encoder = AccountingEncoder()
        fee_dic = encoder.default(obj=discount)
        resp = requests.put(discount_endpoint, json=fee_dic)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('PUT ' + discount_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    def delete_discount(self, provider_id, infra_id, resource_id):
        discount_endpoint = self.endpoint + 'providers/' + str(provider_id) + '/infrastructures/' + \
                            str(infra_id) + '/resources/' + str(resource_id) + '/discount'
        resp = requests.delete(discount_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + discount_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Resource consumption record REST API client
    def get_consumption_records_per_workflow(self, workflow_id):
        records_endpoint = self.endpoint + 'consumption/records/workflow/' + str(workflow_id)
        resp = requests.get(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        records = []
        if resp.json() is not None:
            for item in resp.json():
                record = self.read_record(item)
                records.append(record)
        return records

    def get_consumption_records_per_task_in_workflow(self, workflow_id, task_id):
        records_endpoint = self.endpoint + 'consumption/records/workflow/' + str(workflow_id) + '/task/' + str(task_id)
        resp = requests.get(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        records = []
        if resp.json() is not None:
            for item in resp.json():
                record = self.read_record(item)
                records.append(record)
        return records

    def get_consumption_records_per_reporter(self, reporter_id):
        records_endpoint = self.endpoint + 'consumption/records/reporter/' + str(reporter_id)
        resp = requests.get(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        records = []
        if resp.json() is not None:
            for item in resp.json():
                record = self.read_record(item)
                records.append(record)
        return records

    def get_consumption_records_per_user(self, user_id):
        records_endpoint = self.endpoint + 'consumption/records/user/' + str(user_id)
        resp = requests.get(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        records = []
        if resp.json() is not None:
            for item in resp.json():
                record = self.read_record(item)
                records.append(record)
        return records

    def get_consumption_records_per_transaction(self, start_timestamp, stop_timestamp):
        records_endpoint = self.endpoint + 'consumption/records/transaction/' + str(start_timestamp) + '/' + str(stop_timestamp)
        resp = requests.get(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('GET ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        records = []
        if resp.json() is not None:
            for item in resp.json():
                record = self.read_record(item)
                records.append(record)
        return records

    def add_consumption_record(self, record):
        records_endpoint = self.endpoint + 'consumption/records'
        encoder = AccountingEncoder()
        record_dic = encoder.default(obj=record)
        resp = requests.post(records_endpoint, json=record_dic)
        if resp.status_code != 201:
            # Request error
            raise HTTPError('POST ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))
        else:
            return self.read_record(resp.json())

    def delete_consumption_record(self, record):
        records_endpoint = self.endpoint + 'consumption/records/' + str(record.id)
        resp = requests.delete(records_endpoint)
        if resp.status_code != 200:
            # Request error
            raise HTTPError('DELETE ' + records_endpoint + '. Code: {code}. Message {message}'
                            .format(code=resp.status_code, message=resp.content))

    # Common methods to parse model objects
    def read_feed(self, json):
        # read resources from json
        amount = None
        if json["amount"] is not None:
            amount = ResourceAmount(**json["amount"])
        discount = None
        if json["discount"] is not None:
            discount = Discount(**json["discount"])
        fee = ResourceFee(json['value'], json['currency'], amount, discount, json['id'], json['resource_id'])
        return fee

    def read_resource(self, json):
        # read resources (and nested objects) from json
        fee = None
        if 'fee' in json:
            fee = self.read_feed(json["fee"])
        resource = Resource(json['name'], json['type'], fee, json['id'], json['infrastructure_id'])
        return resource

    def read_infrastructure(self, json):
        # read resources (and nested objects) from json
        resources = []
        for item in json["resources"]:
            res = self.read_resource(item)
            resources.append(res)
        infra = Infrastructure(json['name'], json['server'], json['type'], resources, json['id'], json['provider_id'])
        return infra

    def read_provider(self, json):
        # read providers (and nested objects) from json
        infrastructures = []
        for item in json["infrastructures"]:
            infra = self.read_infrastructure(item)
            infrastructures.append(infra)
        provider = Provider(json['name'], infrastructures, json['id'])
        return provider

    def read_record(self, json):
        consumptions = []
        if 'consumptions' in json and json['consumptions'] is not None:
            for consumption in json['consumptions']:
                consumptions.append(self.read_consumption(consumption))

        start_transaction = None
        if 'start_transaction' in json and json['start_transaction'] is not None:
            try:
                start_transaction = datetime.strptime(json['start_transaction'], '%Y-%m-%d %H:%M:%S.%f')
            except Exception as err:
                start_transaction = datetime.strptime(json['start_transaction'], '%Y-%m-%d %H:%M:%S')

        stop_transaction = None
        if 'stop_transaction' in json and json['stop_transaction'] is not None:
            try:
                stop_transaction = datetime.strptime(json['stop_transaction'], '%Y-%m-%d %H:%M:%S.%f')
            except Exception as err:
                stop_transaction = datetime.strptime(json['stop_transaction'], '%Y-%m-%d %H:%M:%S')

        workflow_id = None
        if 'workflow_id' in json:
            workflow_id = json['workflow_id']

        task_id = None
        if 'task_id' in json:
            task_id = json['task_id']

        workflow_parameters = None
        if 'workflow_parameters' in json:
            workflow_parameters = json['workflow_parameters']

        user_id = None
        if 'user_id' in json:
            user_id = json['user_id']

        reporter_id = None
        if 'reporter_id' in json:
            reporter_id = json['reporter_id']

        id = None
        if 'id' in json:
            id = json['id']

        record = ResourceConsumptionRecord(start_transaction, stop_transaction, workflow_id, task_id,
                                           workflow_parameters, consumptions, user_id, reporter_id, id)
        return record

    def read_consumption(self, json):
        value = None
        if 'value' in json:
            value = json['value']

        unit = None
        if 'unit' in json:
            unit = json['unit']

        record_id = None
        if 'record_id' in json:
            record_id = json['record_id']

        resource_id = None
        if 'resource_id' in json:
            resource_id = json['resource_id']

        unit = None
        if 'id' in json:
            unit = json['id']

        consumption = ResourceConsumption(value, unit, record_id, resource_id, id)
        return consumption
