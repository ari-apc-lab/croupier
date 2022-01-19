"""
Copyright (c) 2022 ATOS. All rights reserved.

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

@author: Yosu Gorronogoitia
         Atos Spain S.A.
         e-mail: jesus.gorronogoitia@atos.net

pycompss.py
"""
from croupier_plugin.infrastructure_interfaces.infrastructure_interface import InfrastructureInterface
from croupier_plugin.ssh import SshClient
from past.builtins import basestring


class Pycompss(InfrastructureInterface):
    def _parse_job_settings(self, job_id, job_settings, script=False, timezone=None):
        # Not required
        pass

    def _get_jobid(self, output):
        return output.split(' ')[-1].strip()

    def _build_job_cancellation_call(self, name, job_settings):
        """
        Creates the PyCOMPSs job cancellation command
        """
        pass

    def get_states(self, ssh_config, job_names):
        """
        Uses PyCOMPSs Manager for getting job state and accounting audits
        """
        pass

    def delete_reservation(self, ssh_client, reservation_id, deletion_path):
        # Not required
        pass

    def _add_audit(self, job_id, job_settings, script=False, ssh_client=None):
        # Not supported
        pass

    def submit_job(self,
                   ssh_client,
                   name,
                   job_settings,
                   is_singularity,
                   context=None,
                   environment=None,
                   timezone=None):
        """
        Sends a job to the HPC

        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @rtype string
        @param context: cloudify context
        @type context: cloudify.ctx
        @param environment: Dictionary containing context env vars
        @type environment: dictionary of strings
        @param timezone: Timezone of the HPC the job is being submitted to
        @rtype string
        @return Slurm's job id sent. None if an error arise.
        """
        if not SshClient.check_ssh_client(ssh_client, self.logger):
            self.logger.error('check_ssh_client failed')
            return False

        # build the command to submit the job
        submission_command = self._build_job_submission_call(name, job_settings, ssh_client, timezone=timezone)

        if 'error' in submission_command:
            self.logger.error("Couldn't build the command to send the PyCOMPSs job: " + submission_command['error'])
            return False

        # submit the job
        command = submission_command['command']

        output, exit_code = ssh_client.execute_shell_command(command, env=environment, workdir=self.workdir,
                                                             wait_result=True)
        if exit_code != 0:
            self.logger.error("Job submission '" + command + "' exited with code " + str(exit_code) + ":\n" + output)
            return False

        return self._get_jobid(output)

    def _build_job_submission_call(self, name, job_settings, ssh_client, timezone):
        """
        Generates submission command line as a string
        submission call:
        export COMPSS_PYTHON_VERSION=3
        module load COMPSs/2.10
        pycompss job submit -e [ENV_VAR...] -app APP_NAME [COMPSS_ARGS] APP_FILE [APP_ARGS]

        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @rtype dict
        @return dict with possible keys:
         'command' string to call pycompss with its parameters
          'error' if an error arise.
        """
        response = {}
        # check input information correctness
        if not isinstance(job_settings, dict) or \
                not isinstance(name, basestring):
            return {'error': "Incorrect inputs"}
        if 'app_name' not in job_settings:
            return {'error': "app_name not provided"}
        if 'app_file' not in job_settings:
            return {'error': "app_file not provided"}

        # Build PyCOMPSs submission command from job_settings
        _command = 'export COMPSS_PYTHON_VERSION=3; module load COMPSs/2.10; pycompss job submit'

        if 'env' in job_settings:
            for env_entry in job_settings['env']:
                for key in env_entry:
                    _command += ' -e ' + key + '=' + str(env_entry[key])

        _command += ' -app ' + job_settings['app_name']

        if 'compss_args' in job_settings:
            for key in job_settings['compss_args']:
                _command += ' --' + key + '=' + str(job_settings['compss_args'][key])

        _command += ' ' + job_settings['app_file']

        if 'app_args' in job_settings:
            for arg in job_settings['app_args']:
                _command += ' ' + str(arg)

        response['command'] = _command
        return response
