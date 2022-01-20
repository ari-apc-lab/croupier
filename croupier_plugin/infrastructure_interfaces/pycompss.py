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
from cloudify.exceptions import NonRecoverableError

from croupier_plugin.infrastructure_interfaces.infrastructure_interface import InfrastructureInterface, \
    get_prevailing_state
from croupier_plugin.infrastructure_interfaces.slurm import start_time_tostr, get_job_metrics, _parse_audit_metrics, \
    _parse_states
from croupier_plugin.ssh import SshClient
from past.builtins import basestring


def get_job_metrics(job_name, ssh_client, workdir, logger):
    # Get job execution audits for monitoring metrics
    audits = {}
    audit_metrics = "JobID,JobName,User,Partition,ExitCode,Submit,Start,End,TimeLimit,CPUTimeRaw,NCPUS"
    audit_command = "sacct --name {job_name} -o {metrics} -p --noheader -X" \
        .format(job_name=job_name, metrics=audit_metrics)

    output, exit_code = ssh_client.execute_shell_command(
        audit_command,
        workdir=workdir,
        wait_result=True)
    if exit_code == 0:
        audits = _parse_audit_metrics(output)
    else:
        logger.error("Failed to get job metrics")
    return audits


class Pycompss(InfrastructureInterface):
    def initialize(self, credentials, ssh_client):
        if "host" not in credentials:
            message = "PyCOMPSs Initialization: host not located in credentials"
            self.logger.error(message)
            raise NonRecoverableError(str(message))
        if "user" not in credentials:
            message = "PyCOMPSs Initialization: user not located in credentials"
            self.logger.error(message)
            raise NonRecoverableError(str(message))
        host = credentials["host"]
        user = credentials["user"]

        # Build PyCOMPSs initialization command
        _command = 'export COMPSS_PYTHON_VERSION=3; module load COMPSs/2.10; ' \
                   'pycompss init cluster -l {user}@{host}'.format(user=user, host=host)

        # Execute PyCOMPSs initialization
        msg, exit_code = ssh_client.execute_shell_command(_command, wait_result=True)

        if exit_code != 0:
            ssh_client.close_connection()
            raise NonRecoverableError(
                "Failed PyCOMPSs initialization on the infrastructure with exit code: {code} and msg: {msg}".format(
                    code=str(exit_code), msg=msg)
            )

    def deploy_app(self, job_settings, workdir, ssh_client):
        if 'app_name' not in job_settings:
            message = "PyCOMPSs Initialization: app_name not located in job_options"
            self.logger.error(message)
            raise NonRecoverableError(str(message))
        if 'app_source' not in job_settings:
            message = "PyCOMPSs Initialization: app_source not located in job_options"
            self.logger.error(message)
            raise NonRecoverableError(str(message))

        app_source: str = job_settings["app_source"]
        if not app_source.startswith("/"):
            app_source = "$HOME/" + app_source

        # Build PyCOMPSs app deployment command
        _command = 'export COMPSS_PYTHON_VERSION=3; module load COMPSs/2.10; ' \
                   'pycompss app deploy {app_name} --local_source {local_source} --remote_dir {remote_dir}'.format(
            app_name=job_settings["app_name"], local_source=app_source, remote_dir=workdir)

        # Execute PyCOMPSs app deployment
        msg, exit_code = ssh_client.execute_shell_command(_command, wait_result=True)

        if exit_code != 0:
            ssh_client.close_connection()
            raise NonRecoverableError(
                "Failed PyCOMPSs app deployment on the infrastructure with exit code: {code} and msg: {msg}".format(
                    code=str(exit_code), msg=msg)
            )

    def _parse_job_settings(self, job_id, job_settings, script=False, timezone=None):
        # Not required
        pass

    def _get_jobid(self, output):
        return output.split('\n')[0].split(' ')[-1].strip()

    def _build_job_cancellation_call(self, name, job_settings):
        """
        Creates the PyCOMPSs job cancellation command
        """
        pass

    def get_states(self, credentials, job_names):
        """
        Uses PyCOMPSs Manager|SLURM for getting job state and accounting audits
        sacct -o jobname,state -n -X -P --name <job_name>
        croupierjob_sqq4ic|FAILED
        """
        call = "sacct -o jobname,state -n -X -P --name " + ''.join(job_names)

        client = SshClient(credentials)

        output, exit_code = client.execute_shell_command(call, workdir=self.workdir, wait_result=True)
        states = {}
        if exit_code == 0:
            states = _parse_states(output, self.logger)
        else:
            self.logger.error("Failed to get job states: " + output)

        # Get job execution audits for monitoring metrics
        audits = {}
        for name in job_names:
            if name in states:
                if states[name] != 'PENDING':
                    audits[name] = get_job_metrics(name, client, self.workdir, self.logger)
            else:
                self.logger.warning("Could not parse the state of job: " + name + "Parsed dict:" + str(states))

        client.close_connection()

        return states, audits

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
        _command += ' --job_name=' + name

        _command += ' ' + job_settings['app_file']

        if 'app_args' in job_settings:
            for arg in job_settings['app_args']:
                _command += ' ' + str(arg)

        response['command'] = _command
        return response
