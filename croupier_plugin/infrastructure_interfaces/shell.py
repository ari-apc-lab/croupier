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

bash.py
'''


from croupier_plugin.ssh import SshClient
from croupier_plugin.infrastructure_interfaces import infrastructure_interface


class Shell(infrastructure_interface.InfrastructureInterface):

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False):
        _settings = ''

        # add executable and arguments
        if not script:
            _settings += ' ./' + job_settings['script']
            if 'arguments' in job_settings:
                for arg in job_settings['arguments']:
                    _settings += ' '+arg
            _settings += '; '

            _settings += 'echo ' + job_id + ',$? >> croupier-monitor.data; '

        return {'data': _settings}

    def _build_job_cancellation_call(self, name, job_settings, logger):
        return "pkill -f " + name

# Monitor
    def get_states(self, workdir, credentials, job_names, logger):

        call = "cat croupier-monitor.data"

        client = SshClient(credentials)

        output, exit_code = client.execute_shell_command(
            call,
            workdir=workdir,
            wait_result=True)

        client.close_connection()

        states = {}
        audits = {}
        if exit_code == 0:
            states = self._parse_states(output, logger)
        for job_name in job_names:
            audits[job_name] = None

        return states, audits

    def _parse_states(self, raw_states, logger):
        """ Parse two colums exit codes into a dict """
        jobs = raw_states.splitlines()
        parsed = {}
        if jobs and (len(jobs) > 1 or jobs[0] != ''):
            for job in jobs:
                first, second = job.strip().split(',')
                parsed[first] = self._parse_exit_codes(second)

        return parsed

    def _parse_exit_codes(self, exit_code):
        if exit_code == '0':  # exited normally
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.COMPLETED]
        elif exit_code == '1':  # general error
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.FAILED]
        elif exit_code == '126':  # cannot execute
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.REVOKED]
        elif exit_code == '127':  # not found
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.BOOTFAIL]
        elif exit_code == '130':  # terminated by ctrl+c
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.CANCELLED]
        else:
            return infrastructure_interface.JOBSTATESLIST[infrastructure_interface.FAILED]
