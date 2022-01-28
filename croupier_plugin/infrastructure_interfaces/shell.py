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

bash.py
"""


from croupier_plugin.ssh import SshClient
from croupier_plugin.infrastructure_interfaces import infrastructure_interface


class Shell(infrastructure_interface.InfrastructureInterface):

    def _get_jobid(self, output):
        if output:
            return output.split(' ')[-1].strip()
        else:
            return "NO_RESPONSE"

    def _build_job_submission_call(self, name, job_settings, ssh_client, timezone):
        """
        Generates submission command line as a string

        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @rtype dict
        @return dict with two keys:
         'call' string to call slurm with its parameters, and
         'scale_env_mapping_call' to push the scale env variables on
         the batch scripts
            None if an error arise.
        """
        # Build single line command
        script_name = job_settings['script']
        args = ''
        if 'arguments' in job_settings:
            for arg in job_settings['arguments']:
                args += arg + ' '

        script_name = script_name if '/' in script_name else './' + script_name

        call_script_content = "#!/bin/bash\n" \
                              "nohup {script_name} {args}>{name}.out 2>{name}.err &\n" \
                              "pid=$!\n" \
                              "wait $pid\n" \
                              "exit_code=$?\n" \
                              "echo {name},$exit_code >> croupier-monitor.dat".\
            format(script_name=script_name, name=name, args=args)
        call_name = name + "_call.sh"
        if not self.create_shell_script(ssh_client, call_name, call_script_content):
            return {'error': 'could not create the call script'}

        _call = "nohup ./{call_name} >/dev/null 2>/dev/null &".format(call_name=call_name)

        response = {'call': _call}

        return response

    def _build_job_cancellation_call(self, name, job_settings):
        return "pkill -f " + name

# Monitor
    def get_states(self, credentials, job_names):
        call = "cat croupier-monitor.dat"

        client = SshClient(credentials)

        output, exit_code = client.execute_shell_command(
            call,
            workdir=self.workdir,
            wait_result=True)

        client.close_connection()

        states = {}
        audits = {}
        if exit_code == 0:
            states = self._parse_states(output)
        for job_name in job_names:
            audits[job_name] = {}

        return states, audits

    def _parse_states(self, raw_states):
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
