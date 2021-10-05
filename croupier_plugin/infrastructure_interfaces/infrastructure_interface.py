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

infrastructure_interface.py
'''
from builtins import str
from builtins import range
from past.builtins import basestring
from builtins import object
import io
import os
import string
import random
from datetime import datetime
from croupier_plugin.ssh import SshClient

BOOTFAIL = 0
CANCELLED = 1
COMPLETED = 2
CONFIGURING = 3
COMPLETING = 4
FAILED = 5
NODEFAIL = 6
PENDING = 7
PREEMPTED = 8
REVOKED = 9
RUNNING = 10
SPECIALEXIT = 11
STOPPED = 12
SUSPENDED = 13
TIMEOUT = 14

JOBSTATESLIST = [
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "CONFIGURING",
    "COMPLETING",
    "FAILED",
    "NODE_FAIL",
    "PENDING",
    "PREEMPTED",
    "REVOKED",
    "RUNNING",
    "SPECIAL_EXIT",
    "STOPPED",
    "SUSPENDED",
    "TIMEOUT",
]

JOBSTATESDICT = {
    "BOOT_FAIL": 0,
    "CANCELLED": 1,
    "COMPLETED": 2,
    "CONFIGURING": 3,
    "COMPLETING": 4,
    "FAILED": 5,
    "NODE_FAIL": 6,
    "PENDING": 7,
    "PREEMPTED": 8,
    "REVOKED": 9,
    "RUNNING": 10,
    "SPECIAL_EXIT": 11,
    "STOPPED": 12,
    "SUSPENDED": 13,
    "TIMEOUT": 14,
}

_STATES_PRECEDENCE = [
    FAILED,
    NODEFAIL,
    BOOTFAIL,
    CANCELLED,
    REVOKED,
    TIMEOUT,
    SPECIALEXIT,
    STOPPED,
    SUSPENDED,
    PREEMPTED,
    RUNNING,
    CONFIGURING,
    PENDING,
    COMPLETING,
    COMPLETED
]


def state_int_to_str(value):
    """state on its int value to its string value"""
    return JOBSTATESLIST[int(value)]


def state_str_to_int(value):
    """state on its string value to its int value"""
    return JOBSTATESDICT[value]


def get_prevailing_state(state1, state2):
    """receives two string states and decides which one prevails"""
    _st1 = state_str_to_int(state1)
    _st2 = state_str_to_int(state2)

    if _st1 == _st2:
        return state1

    for state in _STATES_PRECEDENCE:
        if _st1 == state or _st2 == state:
            return JOBSTATESLIST[state]

    return state1


class InfrastructureInterface(object):
    infrastructure_interface = None

    def __init__(self, infrastructure_interface, monitor_start_time=None):
        self.infrastructure_interface = infrastructure_interface
        self.monitor_start_time = monitor_start_time
        # self.audit_inserted = False

    @staticmethod
    def factory(infrastructure_interface, monitor_start_time=None):
        if infrastructure_interface == "SLURM":
            from croupier_plugin.infrastructure_interfaces.slurm import Slurm
            return Slurm(infrastructure_interface, monitor_start_time)
        if infrastructure_interface == "TORQUE":
            from croupier_plugin.infrastructure_interfaces.torque import Torque
            return Torque(infrastructure_interface)
        if infrastructure_interface == "PBSPRO":
            from croupier_plugin.infrastructure_interfaces.pbspro import Pbspro
            return Pbspro(infrastructure_interface)
        if infrastructure_interface == "SHELL":
            from croupier_plugin.infrastructure_interfaces.shell import Shell
            return Shell(infrastructure_interface)
        return None

    def submit_job(self,
                   ssh_client,
                   name,
                   job_settings,
                   is_singularity,
                   logger,
                   workdir=None,
                   context=None,
                   timezone=None):
        """
        Sends a job to the HPC

        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @type is_singularity: bool
        @param is_singularity: True if the job is in a container
        @rtype string
        @param logger: Logger object to print log messages
        @rtype logger
        @param workdir: Path of the working directory of the job
        @rtype string
        @param context: Dictionary containing context env vars
        @rtype dictionary of strings
        @param timezone: Timezone of the HPC the job is being submitted to
        @rtype string
        @return Slurm's job id sent. None if an error arise.
        """
        if not SshClient.check_ssh_client(ssh_client, logger):
            logger.error('check_ssh_client failed')
            return False

        # Build script if there is no one, or Singularity
        # self.audit_inserted = False
        if 'script' not in job_settings or is_singularity:
            # generate script content
            if is_singularity:
                script_content = self._build_container_script(
                    name,
                    job_settings,
                    workdir,
                    ssh_client,
                    logger)
            else:
                script_content = self._build_script(name, job_settings, workdir, ssh_client, logger)

            if script_content is None:
                logger.error('script_content is None')
                return False

            if not self.create_shell_script(
                    ssh_client,
                    name + ".script",
                    script_content,
                    logger,
                    workdir=workdir):
                logger.error('_create_shell_script failed')
                return False

            # @TODO: use more general type names (e.g., BATCH/INLINE, etc)
            settings = {
                "script": name + ".script"
            }

            if 'arguments' in job_settings:
                settings['arguments'] = job_settings['arguments']

            if 'scale' in job_settings:
                settings['scale'] = job_settings['scale']
                if 'scale_max_in_parallel' in job_settings:
                    settings['scale_max_in_parallel'] = \
                        job_settings['scale_max_in_parallel']
        else:
            settings = job_settings

        # build the call to submit the job
        response = self._build_job_submission_call(name, settings, timezone=timezone)

        if 'error' in response:
            logger.error(
                "Couldn't build the call to send the job: " +
                response['error'])
            return False

        # prepare the scale env variables
        if 'scale_env_mapping_call' in response:
            scale_env_mapping_call = response['scale_env_mapping_call']
            output, exit_code = ssh_client.execute_shell_command(
                scale_env_mapping_call,
                workdir=workdir,
                wait_result=True)
            if exit_code != 0:
                logger.error("Scale env vars mapping '" +
                             scale_env_mapping_call +
                             "' failed with code " +
                             str(exit_code) + ":\n" + output)
                return False

        # submit the job
        call = response['call']

        output, exit_code = ssh_client.execute_shell_command(
            call,
            env=context,
            workdir=workdir,
            wait_result=True)
        if exit_code != 0:
            logger.error("Job submission '" + call + "' exited with code " +
                         str(exit_code) + ":\n" + output)
            return False
        return output.split(' ')[-1].strip()

    def clean_job_aux_files(self,
                            ssh_client,
                            name,
                            job_options,
                            is_singularity,
                            logger,
                            workdir=None):
        """
        Cleans no more needed job files in the HPC

        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @type is_singularity: bool
        @param is_singularity: True if the job is in a container
        @rtype string
        @return Slurm's job name stopped. None if an error arise.
        """
        if not SshClient.check_ssh_client(ssh_client, logger):
            return False

        if is_singularity:
            return ssh_client.execute_shell_command(
                "rm " + name + ".script",
                workdir=workdir)
        return True

    def stop_job(self,
                 ssh_client,
                 name,
                 job_options,
                 is_singularity,
                 logger,
                 workdir=None):
        """
        Stops a job from the HPC

        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @type name: string
        @param name: Job name
        @type job_options: dictionary
        @param job_options: dictionary with the job options
        @type is_singularity: bool
        @param is_singularity: True if the job is in a container
        @rtype string
        @return Slurm's job name stopped. None if an error arise.
        """
        if not SshClient.check_ssh_client(ssh_client, logger):
            return False

        call = self._build_job_cancellation_call(name,
                                                 job_options,
                                                 logger)
        if call is None:
            return False

        return ssh_client.execute_shell_command(
            call,
            workdir=workdir)

    def create_new_workdir(self, ssh_client, base_dir, base_name, logger):
        workdir = self._get_time_name(base_name)

        # we make sure that the workdir does not exists
        base_name = workdir
        while self._exists_path(ssh_client, base_dir + "/" + workdir):
            workdir = self._get_random_name(base_name)

        full_path = base_dir + "/" + workdir
        if ssh_client.execute_shell_command(
                "mkdir -p " + base_dir + "/" + workdir):
            return full_path
        else:
            logger.warning("Failed to create '" + base_dir +
                           "/" + workdir + "' directory.")
            return None

    #   ################ ABSTRACT METHODS ################

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False,
            timezone=None):
        """
        Generates specific manager data accouding to job_settings

        @type job_id: string
        @param job_id: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @rtype dict
        @return dict with two keys:
         'data' parsed data with its parameters, and
         'error' if an error arise.
        """
        raise NotImplementedError(
            "'_parse_job_settings' not implemented.")

    def _build_job_cancellation_call(self,
                                     name,
                                     job_settings,
                                     logger):
        """
        Generates cancel command line as a string

        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @rtype string
        @return string to call slurm with its parameters.
            None if an error arise.
        """
        raise NotImplementedError(
            "'_build_job_cancellation_call' not implemented.")

    def _get_envar(
            self,
            envar,
            default):
        """
        Returns the WM specific envar, or default if there is no one

        @type envar: string
        @param name: Orchestrator env variable
        @type default: ANY
        @param default: default value if WM has no mach
        @rtype ANY
        @return envar WM specifc if present, else default
        """
        raise NotImplementedError(
            "'_get_envar' not implemented.")

    # Monitor
    def get_states(self, workdir, credentials, job_names, logger):
        """
        Get the states of the jobs names
        @type workdir: string
        @param workdir: Working directory in the HPC
        @type credentials: dictionary
        @param credentials: SSH ssh_config to connect to the HPC
        @type job_names: list
        @param job_names: list of the job names to retrieve their states
        @rtype dict
        @return a dictionary of job names and its states
        """
        raise NotImplementedError("'get_states' not implemented.")

    #   ##################################################

    def delete_reservation(self, ssh_client, reservation_id, deletion_path):
        """
        Deletes a reservation
        @type ssh_client: SshClient
        @param ssh_client: ssh client connected to an HPC login node
        @type reservation_id: string
        @param reservation_id: ID of the reservation to delete
        @type deletion_path: string
        @param deletion_path: Path where the executable that deletes reservations resides in the HPC
        """
        raise NotImplementedError("'delete_reservation' not implemented for this interface.")

    def _build_script(self, name, job_settings, workdir, ssh_client, logger, container=False):
        """
        Creates a script to run batch jobs

        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the container job options
        @rtype string
        @return string with the batch script. None if an error arise.
        """
        # check input information correctness
        if not container:
            if not isinstance(job_settings, dict) or \
                    not isinstance(name, basestring):
                logger.error("Batch job settings malformed")
                return None

            if 'commands' not in job_settings or \
                    not job_settings['commands'] or \
                    'max_time' not in job_settings:
                logger.error("Batch job settings malformed. commands or max_time missing")
                return None
        else:
            if not isinstance(job_settings, dict) or \
                    not isinstance(name, basestring):
                logger.error("Singularity settings malformed")
                return None

            if 'image' not in job_settings or \
                    'commands' not in job_settings or \
                    'max_time' not in job_settings:
                logger.error("Singularity settings malformed")
                return None

        script = '#!/bin/bash -l\n\n'

        response = self._parse_job_settings(
            name,
            job_settings,
            script=True)

        # TODO Add extra audit support to response
        # if not self.audit_inserted:
        #     response = self._add_audit(
        #         name, job_settings=response, script=False, ssh_client=ssh_client, workdir=workdir, logger=logger)

        if 'error' in response and response['error']:
            logger.error(response['error'])
            return None

        script += response['data']

        script += '\n# DYNAMIC VARIABLES\n\n'

        # Force use WORKDIR
        script += 'cd $CURRENT_WORKDIR\n\n'

        # NOTE an uploaded script could also be interesting to execute
        if 'pre' in job_settings:
            for entry in job_settings['pre']:
                script += entry + '\n'
            script += '\n'

        if not container:
            for cmd in job_settings['commands']:
                script += cmd + '\n'
        else:
            script += 'mpirun singularity exec '

            if 'home' in job_settings and job_settings['home'] != '':
                script += '-H ' + job_settings['home'] + ' '

            if 'volumes' in job_settings:
                for volume in job_settings['volumes']:
                    script += '-B ' + volume + ' '

            # add executable and arguments
            script += job_settings['image'] + ' '
            separator = ' && '
            script += separator.join(job_settings['commands']) + '\n'

        # NOTE an uploaded script could also be interesting to execute
        if 'post' in job_settings:
            for entry in job_settings['post']:
                script += entry + '\n'
            script += '\n'

        return script

    def _build_job_submission_call(self, name, job_settings, timezone):
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
        # check input information correctness
        if not isinstance(job_settings, dict) or \
                not isinstance(name, basestring):
            return {'error': "Incorrect inputs"}

        if 'commands' not in job_settings and \
                'script' not in job_settings:
            return {'error': "'commands' or 'script' " +
                             "must be defined in job settings"}

        # Build single line command
        _call = ''

        # NOTE an uploaded script could also be interesting to execute
        if 'pre' in job_settings:
            for entry in job_settings['pre']:
                _call += entry + '; '

        response = self._parse_job_settings(
            name,
            job_settings,
            timezone=timezone)

        # TODO Add extra audit support
        # if not self.audit_inserted:
        #     response = self._add_audit(
        #         name, job_settings=response, script=True, ssh_client=ssh_client, workdir=workdir, logger=logger)

        if 'error' in response and response['error']:
            return response

        _call += response['data']

        # NOTE an uploaded script could also be interesting to execute
        if 'post' in job_settings:
            for entry in job_settings['post']:
                _call += entry + '; '

        if self.__class__.__name__ == 'Shell':
            # Run in the background detached from terminal
            _call = 'nohup sh -c "' + _call + '" &'

        response = {'call': _call}

        # map orchestrator variables into script
        if 'scale' in job_settings and int(job_settings['scale']) > 1:

            # set the max of parallel jobs
            scale_max = job_settings['scale']

            # set the job array
            if 'scale_max_in_parallel' in job_settings and \
                    int(job_settings['scale_max_in_parallel']) > 0:
                scale_max = job_settings['scale_max_in_parallel']

            scale_env_mapping_call = \
                "sed -i '/# DYNAMIC VARIABLES/a\\" \
                "SCALE_INDEX={scale_index}\\n" \
                "SCALE_COUNT={scale_count}\\n" \
                "SCALE_MAX={scale_max}' " \
                "{script}".format(
                    scale_index=self._get_envar('SCALE_INDEX', 0),
                    scale_count=self._get_envar(
                        'SCALE_COUNT', job_settings['scale']),
                    scale_max=self._get_envar('SCALE_MAX', scale_max),
                    script=job_settings['script'].split()[0])  # file name only

            response['scale_env_mapping_call'] = scale_env_mapping_call

        return response

    def create_shell_script(self,
                            ssh_client,
                            name,
                            script_content,
                            logger,
                            workdir=None):
        # @TODO: why not to use ctx.download_resource and
        #        ssh_client.open_sftp().put(...)?
        # escape for echo command
        # Converting script_content to str or array of str
        try:
            script_content = script_content.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        script_data = script_content \
            .replace("\\", "\\\\") \
            .replace("$", "\\$") \
            .replace("`", "\\`") \
            .replace('"', '\\"')

        create_call = "echo \"" + script_data + "\" >> " + name + \
                      "; chmod +x " + name
        _, exit_code = ssh_client.execute_shell_command(
            create_call,
            workdir=workdir,
            wait_result=True)

        if exit_code != 0:
            logger.error(
                "failed to create script: call '" + create_call +
                "', exit code " + str(exit_code))
            return False

        return True

    def _build_container_script(self,
                                name,
                                job_settings,
                                workdir,
                                ssh_client,
                                logger):
        """
        Creates a script to run Singularity

        @type name: string
        @param name: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the container job options
        @rtype string
        @return string with the batch script. None if an error arise.
        """
        return self._build_script(
            name,
            job_settings,
            workdir,
            ssh_client,
            logger,
            container=True
        )

    def _get_random_name(self, base_name):
        """ Get a random name with a prefix """
        return base_name + '_' + self.__id_generator()

    def _get_time_name(self, base_name):
        """ Get a random name with a prefix """
        return base_name + '_' + datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    def __id_generator(self,
                       size=6,
                       chars=string.digits + string.ascii_letters):
        return ''.join(random.SystemRandom().choice(chars)
                       for _ in range(size))

    def _exists_path(self, ssh_client, path):
        _, exit_code = ssh_client.execute_shell_command(
            '[ -d "' + path + '" ]',
            wait_result=True)

        if exit_code == 0:
            return True
        else:
            return False

    def sendScript(self, name, script, permissions, workdir, ssh_client, logger):
        # Create invocation with ssh to send script and set its permissions
        # escape for echo command
        script_data = script \
            .replace("\\", "\\\\") \
            .replace("$", "\\$") \
            .replace("`", "\\`") \
            .replace('"', '\\"')

        create_call = u'echo \"{script_data}\" >> {name}; chmod {permissions} {name}'\
            .format(script_data=script_data, name=name, permissions=permissions)

        _, exit_code = ssh_client.execute_shell_command(
            create_call,
            workdir=workdir,
            wait_result=True)

        if exit_code != 0:
            logger.error(
                "failed to send script: call '" + create_call +
                "', exit code " + str(exit_code))
            return False

        return True

    def _add_audit(self, job_id, job_settings, script=False, ssh_client=None, workdir=None, logger=None):
        """
        Adds extra audit support for job execution

         @type job_id: string
        @param job_id: name of the job
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @type job_settings: dictionary
        @param job_settings: dictionary with the job options
        @type script: boolean
        @param script: whether to apply the audit instructions on a submission script
        @type ssh_client: SshClient
        @param ssh_client: ssh client
        @type workdir: str
        @param workdir: directory where to locate the script
        @type workdir: Logger
        @param workdir: logger to output logs
        @rtype dict
        @return dict with two keys:
         'data' parsed data with its parameters, and
         'error' if an error arise.
        """
        raise NotImplementedError(
            "'_build_job_cancellation_call' not implemented.")
