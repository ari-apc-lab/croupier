'''
Copyright (c) 2019 HLRS. All rights reserved.

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

@author: Sergiy Gogolenko
         High-Performance Computing Center. Stuttgart
         e-mail: hpcgogol@hlrs.de

@author: Yosu Gorronogoitia
         Atos Spain S.A.
         e-mail: jesus.gorronogoitia@atos.net

torque.py
'''
from __future__ import absolute_import

from croupier_plugin.ssh import SshClient
from .infrastructure_interface import InfrastructureInterface
from croupier_plugin.utilities import shlex_quote
import re
import datetime
import time

def getHours(cput):
    return int(cput[:cput.index(':')])


def getMinutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def getSeconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def convert_to_seconds(cput):
    hours = getHours(cput) * 3600 + getMinutes(cput) * 60.0 + getSeconds(cput)
    return hours

class Torque(InfrastructureInterface):
    """ Holds the Torque functions. Acts similarly to the class `Slurm`."""

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False):
        _settings = {'data': ''}
        if script:
            _prefix = '#PBS'
            _suffix = '\n'
        else:
            _prefix = ''
            _suffix = ''

        # TODO writ for script (prefix, suffix ??)

        if not script:
            # qsub command plus job name
            # Read environment, required by some HPC (e.g. HLRS Hawk)
            read_environment = "source /etc/profile; "
            _settings[
                'data'] += read_environment + "qsub -V -N {}".format(
                shlex_quote(job_id))

        # Check if exists and has content
        def _check_job_settings_key(key):
            return key in job_settings and str(job_settings[key]).strip()

        def _add_setting(option, value, op_separator=' '):
            _settings['data'] += '{} {}{}{}{}'.format(
                _prefix, option, op_separator, value, _suffix)

        if not _check_job_settings_key('nodes') and \
                _check_job_settings_key('tasks_per_node'):
            return {'error': "Specified 'tasks_per_node' while"
                             "'nodes' is not specified"}

        if _check_job_settings_key('nodes'):
            node_request = "nodes={}".format(job_settings['nodes'])

            # number of cores requested per node
            # TODO If tasks and no tasks_per_node, then
            # tasks_per_node = tasks/nodes
            if _check_job_settings_key('tasks_per_node'):
                node_request += ':ppn={}'.format(
                    job_settings['tasks_per_node'])

            _add_setting('-l', node_request)

        # HLRS Hawk Torque flags
        # Documentation: https://kb.hlrs.de/platforms/index.php/Batch_System_PBSPro_(Hawk)#Node_types
        if _check_job_settings_key('select'):
            node_request = "select={}".format(job_settings['select'])

            if _check_job_settings_key('node_type'):
                node_request += ':node_type={}'.format(
                    job_settings['node_type'])

            if _check_job_settings_key('mpiprocs'):
                node_request += ':mpiprocs={}'.format(
                    job_settings['mpiprocs'])

            _add_setting('-l', node_request)

        if _check_job_settings_key('max_time'):
            _add_setting('-l', 'walltime={}'.format(job_settings['max_time']))

        if _check_job_settings_key('queue') or \
                _check_job_settings_key('partition'):
            if _check_job_settings_key('queue'):
                queue = job_settings['queue']
            else:
                queue = job_settings['partition']
            _add_setting('-q', shlex_quote(queue))

        if _check_job_settings_key('memory'):
            _add_setting('-l', 'mem={}'.format(job_settings('memory')))

        if _check_job_settings_key('mail_user'):
            _add_setting('-M', job_settings['mail_user'])

        # FIXME make slurm and torque compatible
        # a (aborted)
        # b (when it begins)
        # e (when it ends)
        # f (when it terminates with a non-zero exit code)
        if _check_job_settings_key('mail_type'):
            _add_setting('-m', job_settings['mail_type'])

        if _check_job_settings_key('account'):
            _add_setting('-A', job_settings['account'])

        if _check_job_settings_key('stderr_file'):
            _add_setting('-e', job_settings['stdoutstderr_file_file'])
        else:
            _add_setting('-e', job_id + '.err')

        if _check_job_settings_key('stdout_file'):
            _add_setting('-o', job_settings['stdout_file'])
        else:
            _add_setting('-o', job_id + '.out')

        additional_attributes = {}
        if 'group_name' in job_settings:
            additional_attributes["group_list"] = shlex_quote(
                job_settings['group_name'])

        # add scale, executable and arguments
        if not script:
            if 'scale' in job_settings and \
                    int(job_settings['scale']) > 1:
                # set the job array
                _settings['data'] += ' -t 0-{}'.format(
                    job_settings['scale'] - 1)
                if 'scale_max_in_parallel' in job_settings and \
                        int(job_settings['scale_max_in_parallel']) > 0:
                    _settings['data'] += '%{}'.format(
                        job_settings['scale_max_in_parallel'])

            _settings['data'] += ' ' + job_settings['script']
            if _check_job_settings_key('arguments'):
                args = ''
                for arg in job_settings['arguments']:
                    args += arg + ' '
                _settings['data'] += ' -F "{}"'.format(args)
            _settings['data'] += '; '

        return _settings

    def _add_audit(self, job_id, job_settings, script=False, ssh_client=None, workdir=None, logger=None):
        if script:
            # Read script and add audit header
            pattern = re.compile('([a-zA-Z-9_]*).script')
            script_name = pattern.findall(job_settings['data'])[0]+'.script'

            audit_instruction = "echo ProcessorsPerNode=$(( 1 + $(cat /proc/cpuinfo | grep processor | " \
                                "tail -n1 | cut -d':' -f2 | xargs))) > {workdir}/{job_id}.audit"\
                .format(job_id=job_id, workdir=workdir)

            # Remove previous audit line
            command = "cd {workdir}; sed -i '/ProcessorsPerNode/d' {script_name}" \
                .format(workdir=workdir, script_name=script_name, audit_instruction=audit_instruction)
            result = execute_ssh_command(command, workdir, ssh_client, logger)

            # Add audit line
            command = "cd {workdir}; sed -i -e '$a{audit_instruction}' {script_name}"\
                .format(workdir=workdir, script_name=script_name, audit_instruction=audit_instruction)
            result = execute_ssh_command(command, workdir, ssh_client, logger)
        else:
            # Add audit entry
            job_settings['data'] += \
                "\necho ProcessorsPerNode =$((1 + $(cat /proc/cpuinfo | grep processor | tail -n1 | " \
                "cut -d':' -f2 | xargs))) > {workdir}/{job_id}.audit\n\n".format(job_id=job_id, workdir=workdir)
        return job_settings

    def _build_job_cancellation_call(self, name, job_settings, logger):
        return r"qselect -N {} | xargs qdel".format(shlex_quote(name))

    def _get_envar(self, envar, default):
        if envar == 'SCALE_INDEX':
            return '$PBS_ARRAYID'
        else:
            return default

    # Monitor

    def get_states(self, workdir, credentials, job_names, logger):
        return self._get_states_detailed(
            workdir,
            credentials,
            job_names,
            logger) if job_names else {}

    @staticmethod
    def _get_states_detailed(workdir, credentials, job_names, logger):
        """
        Get job states by job names

        This function uses `qstat` command to query Torque.
        Please don't launch this call very friquently. Polling it
        frequently, especially across all users on the cluster,
        will slow down response times and may bring
        scheduling to a crawl.

        It allows to a precise mapping of Torque states to
        Slurm states by taking into account `exit_code`.
        Unlike `get_states_tabular` it parses output on host
        and uses several SSH commands.
        """
        # identify job ids
        call = "echo {} | xargs -n 1 qselect -N".format(
            shlex_quote(' '.join(map(shlex_quote, job_names))))

        client = SshClient(credentials)

        output, exit_code = client.execute_shell_command(
            call,
            workdir=workdir,
            wait_result=True)
        job_ids = Torque._parse_qselect(output)
        if not job_ids:
            return {}

        # get detailed information about jobs
        call = "qstat -f {}".format(' '.join(map(str, job_ids)))

        output, exit_code = client.execute_shell_command(
            call,
            workdir=workdir,
            wait_result=True)
        client.close_connection()
        try:
            job_states, audits = Torque._parse_qstat_detailed(output)
        except SyntaxError as e:
            logger.warning(
                "cannot parse state response for job ids=[{}]".format(
                    ','.join(map(str, job_ids))))
            logger.warning(
                "{err}\n`qstat -f` output to parse:\n\\[\n{text}\n\\]".format(
                    err=str(e), text=output))
            # TODO: think whether error ignoring is better
            #       for the correct lifecycle
            raise e

        return job_states, audits

    @staticmethod
    def _parse_qselect(qselect_output):
        """ Parse `qselect` output and returns
        list of job ids without host names """
        jobs = qselect_output.splitlines()
        if not jobs or (len(jobs) == 1 and jobs[0] == ''):
            return []
        return [int(job.split('.')[0]) for job in jobs]

    @staticmethod
    def _parse_qstat_detailed(qstat_output):
        from StringIO import StringIO
        jobs = {}
        audits = {}
        for job in Torque._tokenize_qstat_detailed(StringIO(qstat_output)):
            # ignore job['Job_Id'], use identification by name
            name = job.get('Job_Name', '')
            state_code = job.get('job_state', None)
            audit = {}
            if name and state_code:
                if state_code == 'C':
                    # Process timestamps from this format 'Tue Sep 22 13:29:49 2020'
                    # to this one "2020-04-15 01:26:59.000403"
                    start_time = datetime.datetime.strptime(job.get("start_time"), '%a %b %d %H:%M:%S %Y')
                    completion_time = datetime.datetime.strptime(job.get("comp_time"), '%a %b %d %H:%M:%S %Y')
                    queued_time = datetime.datetime.strptime(job.get("qtime"), '%a %b %d %H:%M:%S %Y')
                    audit["start_time"] = time.mktime(start_time.timetuple())
                    audit["completion_time"] = time.mktime(completion_time.timetuple())
                    audit["queued_time"] = time.mktime(queued_time.timetuple())
                    audit["cput"] = convert_to_seconds(job.get("resources_used.cput"))
                    audit["vmem"] = re.findall(r'\d+', job.get("resources_used.vmem")).pop()
                    audit["walltime"] = convert_to_seconds(job.get("resources_used.walltime"))
                    audit["mem"] = re.findall(r'\d+', job.get("resources_used.mem")).pop()
                    audit["energy_used"] = job.get("resources_used.energy_used")
                    pattern = re.compile('-l ([a-zA-Z0-9=:]*)')
                    audit["workflow_parameters"] = ','.join(pattern.findall(job.get("submit_args")))
                    exit_status = int(job.get('exit_status', 0))
                    audit["exit_status"] = exit_status
                    audit["job_id"] = job.get('Job_Id')
                    audit["job_name"] = job.get('Job_Name')
                    audit["job_owner"] = job.get('Job_Owner')
                    audit["queue"] = job.get('queue')
                    state = Torque._job_exit_status.get(
                        exit_status, "FAILED")  # unknown failure by default
                else:
                    state = Torque._job_states[state_code]
            jobs[name] = state
            audits[name] = audit
        return jobs, audits

    @staticmethod
    def _tokenize_qstat_detailed(fp):
        import re
        # regexps for tokenization (buiding AST) of `qstat -f` output
        pattern_attribute_first = re.compile(
            r"^(?P<key>Job Id): (?P<value>(\w|\.)+)", re.M)
        pattern_attribute_next = re.compile(
            r"^    (?P<key>\w+(\.\w+)*) = (?P<value>.*)", re.M)
        pattern_attribute_continue = re.compile(
            r"^\t(?P<value>.*)", re.M)

        # tokenizes stream output and
        job_attr_tokens = {}
        for line_no, line in enumerate(fp.readlines()):
            line = line.rstrip('\n\r')  # strip trailing newline character
            if len(line) > 1:  # skip empty lines
                # find match for the new attribute
                match = pattern_attribute_first.match(line)
                if match:  # start to handle new job descriptor
                    if len(job_attr_tokens) > 0:
                        yield job_attr_tokens
                    job_attr_tokens = {}
                else:
                    match = pattern_attribute_next.match(line)

                if match:  # line corresponds to the new attribute
                    attr = match.group('key').replace(' ', '_')
                    job_attr_tokens[attr] = match.group('value')
                else:  # either multiline attribute or broken line
                    match = pattern_attribute_continue.match(line)
                    if match:  # multiline attribute value continues
                        job_attr_tokens[attr] += match.group('value')
                    elif len(job_attr_tokens[attr]) > 0 \
                            and job_attr_tokens[attr][-1] == '\\':
                        # multiline attribute with newline character
                        job_attr_tokens[attr] = "{0}\n{1}".format(
                            job_attr_tokens[attr][:-1], line)
                    else:
                        raise SyntaxError(
                            'failed to parse l{no}: "{line}"'.format(
                                no=line_no, line=line))
        if len(job_attr_tokens) > 0:
            yield job_attr_tokens

    _job_states = dict(
        # C includes completion by both success and fail: "COMPLETED",
        #     "TIMEOUT", "FAILED","CANCELLED", #"BOOT_FAIL", and "REVOKED"
        C="COMPLETED",  # Job is completed after having run
        E="COMPLETING",  # Job is exiting after having run
        H="PENDING",  # (@TODO like "RESV_DEL_HOLD" in Slurm) Job is held
        Q="PENDING",  # Job is queued, eligible to run or routed
        R="RUNNING",  # Job is running
        T="PENDING",  # (nothng in Slurm) Job is being moved to new location
        W="PENDING",  # (nothng in Slurm) Job is waiting for the time after
        #                  which the job is eligible for execution (`qsub -a`)
        S="SUSPENDED",  # (Unicos only) Job is suspended
        # The latter states have no analogues
        #   "CONFIGURING", "STOPPED", "NODE_FAIL", "PREEMPTED", "SPECIAL_EXIT"
    )

    _job_exit_status = {
        0: "COMPLETED",  # OK             Job execution successful
        -1: "FAILED",  # FAIL1          Job execution failed, before
        #                                   files, no retry
        -2: "FAILED",  # FAIL2          Job execution failed, after
        #                                    files, no retry
        -3: "FAILED",  # RETRY          Job execution failed, do retry
        -4: "BOOT_FAIL",  # INITABT        Job aborted on MOM initialization
        -5: "BOOT_FAIL",  # INITRST        Job aborted on MOM init, chkpt,
        #                                    no migrate
        -6: "BOOT_FAIL",  # INITRMG        Job aborted on MOM init, chkpt,
        #                                    ok migrate
        -7: "FAILED",  # BADRESRT       Job restart failed
        -8: "FAILED",  # CMDFAIL        Exec() of user command failed
        -9: "NODE_FAIL",  # STDOUTFAIL     Couldn't create/open stdout/stderr
        -10: "NODE_FAIL",  # OVERLIMIT_MEM  Job exceeded a memory limit
        -11: "NODE_FAIL",  # OVERLIMIT_WT   Job exceeded a walltime limit
        -12: "TIMEOUT",  # OVERLIMIT_CPUT Job exceeded a CPU time limit
    }

    @staticmethod
    def _get_states_tabular(ssh_client, job_names, logger):
        """
        Get job states by job names

        This function uses `qstat` command to query Torque.
        Please don't launch this call very friquently. Polling it
        frequently, especially across all users on the cluster,
        will slow down response times and may bring
        scheduling to a crawl.

        It invokes `tail/awk` to make simple parsing on the remote HPC.
        """
        # TODO:(emepetres) set start day of consulting
        # @caution This code fails to manage the situation
        #          if several jobs have the same name
        call = "qstat -i `echo {} | xargs -n 1 qselect -N` " \
               "| tail -n+6 | awk '{{ print $4 \"|\" $10 }}'".format(
            shlex_quote(' '.join(map(shlex_quote, job_names))))
        output, exit_code = ssh_client.send_command(call, wait_result=True)

        return Torque._parse_qstat_tabular(output) if exit_code == 0 else {}

    @staticmethod
    def _parse_qstat_tabular(qstat_output):
        """ Parse two colums `qstat` entries into a dict """

        def parse_qstat_record(record):
            name, state_code = map(str.strip, record.split('|'))
            return name, Torque._job_states[state_code]

        jobs = qstat_output.splitlines()
        parsed = {}
        # @TODO: think of catch-and-log parsing exceptions
        if jobs and (len(jobs) > 1 or jobs[0] != ''):
            parsed = dict(map(parse_qstat_record, jobs))

        return parsed


def execute_ssh_command(command, workdir, ssh_client, logger):
    _, exit_code = ssh_client.execute_shell_command(command, workdir=workdir, wait_result=True)
    if exit_code != 0:
        logger.error("failed to execute command '" + command + "', exit code " + str(exit_code))
        return False
    return True
