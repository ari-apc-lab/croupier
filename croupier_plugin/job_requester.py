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

job_requester.py: Holds the functions that requests jobs information
"""


from builtins import object
import time
from threading import Lock

import requests

from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (
    InfrastructureInterface,
    state_int_to_str)


class JobRequester(object):
    """ Safely gets the jobs status when requested """
    class __JobRequester(object):
        _last_time = {}
        _lock = Lock()

        def request(self, monitor_jobs, monitor_start_time, logger):
            """ Retrieves the status of every job"""
            states = {}
            audits = {}

            for host, settings in monitor_jobs.items():
                # Only get info when it is safe
                if host in self._last_time:
                    seconds_to_wait = settings['period'] - \
                        (time.time() - self._last_time[host])
                    if seconds_to_wait > 0:
                        continue

                self._last_time[host] = time.time()

                if settings['type'] == "PROMETHEUS":  # external
                    states, audits = self._get_prometheus(
                        host,
                        settings['config'],
                        settings['names'])
                else:  # internal
                    workdir = settings['workdir']
                    timezone = settings['timezone']
                    interface_type = settings['type']
                    wm = InfrastructureInterface.factory(interface_type, logger, workdir, monitor_start_time, timezone)
                    if wm:
                        states, audits = wm.get_states(settings['config'], settings['names'])
                    else:
                        states, audits = self._no_states(host, interface_type, settings['names'], logger)
            return states, audits

        def _get_prometheus(self, host, config, names):
            states = {}
            url = config['url']
            if len(names) == 1:
                query = (url + '/api/v1/query?query=job_status'
                         '%7Bjob%3D%22' + host +
                         '%22%2Cname%3D%22')
            else:
                query = (url + '/api/v1/query?query=job_status'
                         '%7Bjob%3D%22' + host +
                         '%22%2Cname%3D~%22')
            query += '|'.join(names) + '%22%7D'

            payload = requests.get(query)

            response = payload.json()

            for item in response["data"]["result"]:
                states[item["metric"]["name"]] = state_int_to_str(
                    item["value"][1])

            return states

        def _no_states(self, host, mtype, names, logger):
            logger.error("Monitor of type " +
                         mtype +
                         " not suppported. " +
                         "Jobs [" +
                         ','.join(names) +
                         "] on host '" + host
                         + "' will be considered FAILED.")
            states = {}
            audits = {}
            for name in names:  # TODO cancel those jobs
                states[name] = 'FAILED'
            return states, audits

    instance = None

    def __init__(self):
        if not JobRequester.instance:
            JobRequester.instance = JobRequester.__JobRequester()

    def __getattr__(self, name):
        return getattr(self.instance, name)
