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

slurm.py: Holds the slurm functions
"""
from builtins import str
import datetime, pytz
import time

from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (
    InfrastructureInterface,
    get_prevailing_state)
from croupier_plugin.ssh import SshClient


def _parse_audit_metrics(metrics_string):
    audits = {}
    start_time = None
    completion_time = None
    queued_time = None
    metrics = metrics_string.split('|')
    if metrics[6] is not None and metrics[6] != 'Unknown':
        start_time = datetime.datetime.strptime(metrics[6], '%Y-%m-%dT%H:%M:%S')
    if metrics[7] is not None and metrics[7] != 'Unknown':
        completion_time = datetime.datetime.strptime(metrics[7], '%Y-%m-%dT%H:%M:%S')
    if metrics[5] is not None and metrics[5] != 'Unknown':
        queued_time = datetime.datetime.strptime(metrics[5], '%Y-%m-%dT%H:%M:%S')

    audits["job_id"] = metrics[0]
    audits["job_name"] = metrics[1]
    audits["job_owner"] = metrics[2]
    audits["queue"] = metrics[3]
    audits["exit_status"] = metrics[4].split(':')[0]
    if queued_time is not None:
        audits["queued_time"] = time.mktime(queued_time.timetuple())
    if start_time is not None:
        audits["start_time"] = time.mktime(start_time.timetuple())
    if completion_time is not None:
        audits["completion_time"] = time.mktime(completion_time.timetuple())
    audits["walltime"] = convert_to_seconds(metrics[8])
    audits["cput"] = int(metrics[9])
    audits["ncpus"] = metrics[10]

    return audits


def getHours(cput):
    return int(cput[:cput.index(':')])


def getMinutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def getSeconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def convert_to_seconds(cput):
    hours = getHours(cput) * 3600 + getMinutes(cput) * 60.0 + getSeconds(cput)
    return hours


def _parse_states(raw_states, logger):
    """ Parse two colums sacct entries into a dict """
    jobs = raw_states.splitlines()
    parsed = {}
    if jobs and (len(jobs) > 1 or jobs[0] != ''):
        for job in jobs:
            first, second = job.strip().split('|')
            if first in parsed:
                parsed[first] = get_prevailing_state(parsed[first], second)
            else:
                parsed[first] = second

    return parsed


def get_job_metrics(job_name, ssh_client, workdir, monitor_start_time_str, logger):
    # Get job execution audits for monitoring metrics
    audits = {}
    audit_metrics = "JobID,JobName,User,Partition,ExitCode,Submit,Start,End,TimeLimit,CPUTimeRaw,NCPUS"
    audit_command = "sacct --name {job_name} -o {metrics} -p --noheader -X -S {start_time}" \
        .format(job_name=job_name, metrics=audit_metrics, start_time=monitor_start_time_str)

    output, exit_code = ssh_client.execute_shell_command(
        audit_command,
        workdir=workdir,
        wait_result=True)
    if exit_code == 0:
        audits = _parse_audit_metrics(output)
    else:
        logger.error("Failed to get job metrics")
    return audits


def execute_ssh_command(command, workdir, ssh_client, logger):
    _, exit_code = ssh_client.execute_shell_command(command, workdir=workdir, wait_result=True)
    if exit_code != 0:
        logger.error("failed to execute command '" + command + "', exit code " + str(exit_code))
        return False
    return True


def start_time_tostr(start_time, timezone):
    start_time = start_time.astimezone(pytz.timezone(timezone))
    return start_time.strftime("%m/%d/%y-%H:%M:%S")


class Slurm(InfrastructureInterface):
    """ Slurm Workload Manger Driver """

    def _get_jobid(self, output):
        return output.split(' ')[-1].strip()

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False,
            timezone=None):
        _settings = ''
        if script:
            _prefix = '#SBATCH'
            _suffix = '\n'
        else:
            _prefix = ''
            _suffix = ''

        if not script:
            # sbatch command plus job name
            _settings += "sbatch --parsable -J '" + job_id + "'"

        # Check if exists and has content
        def _check_job_settings_key(key):
            return key in job_settings and str(job_settings[key]).strip()

        if script and not _check_job_settings_key('max_time'):
            return {'error': "Job must define the 'max_time' property"}

        # Slurm settings
        if _check_job_settings_key('nodes'):
            _settings += _prefix + ' -N ' + \
                         str(job_settings['nodes']) + _suffix

        if _check_job_settings_key('tasks'):
            _settings += _prefix + ' -n ' + \
                         str(job_settings['tasks']) + _suffix

        if _check_job_settings_key('tasks_per_node'):
            _settings += _prefix + ' --ntasks-per-node=' + \
                         str(job_settings['tasks_per_node']) + _suffix

        if _check_job_settings_key('max_time'):
            _settings += _prefix + ' -t ' + \
                         str(job_settings['max_time']) + _suffix

        if _check_job_settings_key('partition') or \
                _check_job_settings_key('queue'):
            if _check_job_settings_key('partition'):
                partition = job_settings['partition']
            else:
                partition = job_settings['queue']
            _settings += _prefix + ' -p ' + \
                         str(partition) + _suffix

        if _check_job_settings_key('memory'):
            _settings += _prefix + ' --mem=' + \
                         str(job_settings['memory']) + _suffix

        if _check_job_settings_key('reservation'):
            reservation_id = job_settings['reservation']
            _settings += _prefix + ' --reservation=' + str(reservation_id) + _suffix

        if _check_job_settings_key('qos'):
            _settings += _prefix + ' --qos=' + str(job_settings['qos']) + _suffix

        if _check_job_settings_key('mail_user'):
            _settings += _prefix + ' --mail-user=' + \
                         str(job_settings['mail_user']) + _suffix

        if _check_job_settings_key('mail_type'):
            _settings += _prefix + ' --mail-type=' + \
                         str(job_settings['mail_type']) + _suffix

        if _check_job_settings_key('account'):
            _settings += _prefix + ' -A ' + \
                         str(job_settings['account']) + _suffix

        if _check_job_settings_key('stderr_file'):
            _settings += _prefix + ' -e ' + \
                         str(job_settings['stderr_file']) + _suffix
        else:
            _settings += _prefix + ' -e ' + \
                         str(job_id + '.err') + _suffix

        if _check_job_settings_key('stdout_file'):
            _settings += _prefix + ' -o ' + \
                         str(job_settings['stdout_file']) + _suffix
        else:
            _settings += _prefix + ' -o ' + \
                         str(job_id + '.out') + _suffix

        # add scale, executable and arguments
        if not script:
            if 'scale' in job_settings and \
                    int(job_settings['scale']) > 1:
                # set the job array
                _settings += ' --array=0-{}'.format(job_settings['scale'] - 1)
                if 'scale_max_in_parallel' in job_settings and \
                        int(job_settings['scale_max_in_parallel']) > 0:
                    _settings += '%' + \
                                 str(job_settings['scale_max_in_parallel'])

            _settings += ' ' + job_settings['script']
            if 'arguments' in job_settings:
                for arg in job_settings['arguments']:
                    _settings += ' ' + arg
            _settings += '; '

        return {'data': _settings}

    def _build_job_cancellation_call(self, name, job_settings):
        return "scancel --name " + name

    def _get_envar(self, envar, default):
        if envar == 'SCALE_INDEX':
            return '$SLURM_ARRAY_TASK_ID'
        elif envar == 'SCALE_COUNT':
            return '$SLURM_ARRAY_TASK_COUNT'
        else:
            return default

    # def _add_audit(self, job_id, job_settings, script=False, ssh_client=None, workdir=None, logger=None):
    #     if script:
    #         # Read script and add audit header
    #         pattern = re.compile('([a-zA-Z-9_]*).script')
    #         script_name = pattern.findall(job_settings['data'])[0] + '.script'
    #
    #         audit_instruction = "echo ProcessorsPerNode=$(( 1 + $(cat /proc/cpuinfo | grep processor | " \
    #                             "tail -n1 | cut -d':' -f2 | xargs))) > {workdir}/{job_id}.audit" \
    #             .format(job_id=job_id, workdir=workdir)
    #
    #         # Remove previous audit line
    #         command = "cd {workdir}; sed -i '/ProcessorsPerNode/d' {script_name}" \
    #             .format(workdir=workdir, script_name=script_name, audit_instruction=audit_instruction)
    #         result = execute_ssh_command(command, workdir, ssh_client, logger)
    #
    #         # Add audit line
    #         command = "cd {workdir}; sed -i -e '$a{audit_instruction}' {script_name}" \
    #             .format(workdir=workdir, script_name=script_name, audit_instruction=audit_instruction)
    #         result = execute_ssh_command(command, workdir, ssh_client, logger)
    #     else:
    #         # Add audit entry
    #         job_settings['data'] += \
    #             "\necho ProcessorsPerNode =$((1 + $(cat /proc/cpuinfo | grep processor | tail -n1 | " \
    #             "cut -d':' -f2 | xargs))) > {workdir}/{job_id}.audit\n\n".format(job_id=job_id, workdir=workdir)
    #     self.audit_inserted = True
    #     return job_settings

    # Monitor
    def get_states(self, credentials, job_names):

        monitor_start_time_str = start_time_tostr(self.monitor_start_time, self.timezone)

        call = "sacct -n -o JobName,State -X -P --name=" + ','.join(job_names) + " -S " + monitor_start_time_str

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
                    audits[name] = get_job_metrics(name, client, self.workdir, monitor_start_time_str, self.logger)
            else:
                self.logger.warning("Could not parse the state of job: " + name + "Parsed dict:" + str(states))

        client.close_connection()

        return states, audits

    def delete_reservation(self, client, reservation_id, deletion_path):
        call = 'sudo {0} {1}'.format(deletion_path, reservation_id)
        output, exit_code = client.execute_shell_command(
            call,
            wait_result=True)
        if exit_code == 0:
            return True
        else:
            return False
