"""
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
"""
from __future__ import absolute_import

from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import map
from croupier_plugin.ssh import SshClient
from .infrastructure_interface import InfrastructureInterface
from croupier_plugin.utilities import shlex_quote
import re
import datetime, time


class Pbspro(InfrastructureInterface):
    """ Holds the PBS functions. Acts similarly to the class `Slurm`."""

    def _get_jobid(self, output):
        return output.split(' ')[-1].strip()

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False,
            timezone=None):
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

        # PBSPro flags
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
                _add_setting('-q', shlex_quote(queue))

        if _check_job_settings_key('memory'):
            _add_setting('-l', 'mem={}'.format(job_settings['memory']))

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

    def _build_job_cancellation_call(self, name, job_settings):
        return r"qselect -N {} | xargs qdel".format(shlex_quote(name))

    def _get_envar(self, envar, default):
        if envar == 'SCALE_INDEX':
            return '$PBS_ARRAYID'
        else:
            return default

    # Monitor

    def get_states(self, job_names):
        return self._get_states_detailed(job_names) if job_names else {}

    def _get_states_detailed(self, job_names):
        """
        Get job states by job names

        This function uses `qstat` command to query PBSPro.
        Please don't launch this call very frequently. Polling it
        frequently, especially across all users on the cluster,
        will slow down response times and may bring
        scheduling to a crawl.

        It allows to a precise mapping of Torque states to
        Slurm states by taking into account `exit_code`.
        Unlike `get_states_tabular` it parses output on host
        and uses several SSH commands.
        """
        # identify job ids
        # Read environment, required by some HPC (e.g. HLRS Hawk)
        read_environment = "source /etc/profile > /dev/null 2>&1; "
        call = read_environment + "echo {} | xargs -n 1 qselect -x -N".format(
            shlex_quote(' '.join(map(shlex_quote, job_names))))

        client = SshClient(self.credentials)

        output, exit_code = client.execute_shell_command(
            call,
            workdir=self.workdir,
            wait_result=True)
        job_ids = Pbspro._parse_qselect(output)
        if not job_ids:
            return {}

        # get detailed information about jobs
        call = read_environment + "qstat -x -f {}".format(' '.join(map(str, job_ids)))

        output, exit_code = client.execute_shell_command(
            call,
            workdir=self.workdir,
            wait_result=True)
        client.close_connection()
        try:
            job_states, audits = Pbspro._parse_qstat_detailed(output)
        except SyntaxError as e:
            self.logger.warning(
                "cannot parse state response for job ids=[{}]".format(
                    ','.join(map(str, job_ids))))
            self.logger.warning(
                "{err}\n`qstat -x -f` output to parse:\n\\[\n{text}\n\\]".format(
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
        from io import StringIO
        jobs = {}
        audits = {}
        for job in Pbspro._tokenize_qstat_detailed(StringIO(qstat_output)):
            name = job.get("Job_Id", None)
            state_code = job.get('job_state', None)
            audit = {}
            if name and state_code:
                if state_code == 'F':
                    # Process timestamps from this format 'Tue Sep 22 13:29:49 2020'
                    # to this one "2020-04-15 01:26:59.000403"
                    start_time = datetime.datetime.strptime(job.get("stime"), '%a %b %d %H:%M:%S %Y')
                    completion_time = datetime.datetime.strptime(job.get("mtime"), '%a %b %d %H:%M:%S %Y')
                    queued_time = datetime.datetime.strptime(job.get("qtime"), '%a %b %d %H:%M:%S %Y')
                    audit["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    audit["completion_time"] = completion_time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    audit["queued_time"] = queued_time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    audit["cput"] = convert_to_seconds(job.get("resources_used.cput"))
                    audit["cpupercent"] = job.get("resources_used.cpupercent")
                    audit["ncpus"] = job.get("resources_used.ncpus")
                    audit["vmem"] = remove_trailing_unit(job.get("resources_used.vmem"), 'kb')
                    audit["walltime"] = convert_to_seconds(job.get("resources_used.walltime"))
                    audit["mem"] = remove_trailing_unit(job.get("resources_used.mem"), 'kb')
                    audit["queued_time"] = time.mktime(queued_time.timetuple())
                    audit["completion_time"] = time.mktime(completion_time.timetuple())
                    audit["start_time"] = time.mktime(start_time.timetuple())
                    audit["job_id"] = job.get("Job_Id")
                    audit['job_name'] = job.get("Job_Name")
                    audit["job_owner"] = job.get("Job_Owner")
                    audit["queue"] = job.get("queue")
                    audit["exit_status"] = job.get("Exit_status")
                    audit["mpiprocs"] = job.get("Resource_List.mpiprocs")

                    pattern = re.compile('-l ([a-zA-Z0-9=:]*)')
                    audit["workflow_parameters"] = ','.join(pattern.findall(job.get("Submit_arguments")))
                    exit_status = int(job.get('exit_status', 0))
                    state = Pbspro._job_exit_status.get(
                        exit_status, "FAILED")  # unknown failure by default
                else:
                    state = Pbspro._job_states[state_code]
            jobs[name] = state
            audits[name] = audit
        return jobs, audits

    @staticmethod
    def _tokenize_qstat_detailed(fp):
        import re
        # regexps for tokenization (buiding AST) of `qstat -x -f` output
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
        F="FINISH",  # Job is finished
        E="EXITING",  # Job is exiting after having run
        H="PENDING",  # Job is held
        Q="PENDING",  # Job is queued
        R="RUNNING",  # Job is running
        T="PENDING",  # Job is being moved to new location
        W="PENDING",  # Job is waiting for its submitter-assigned start time to be reached
        S="SUSPENDED",  # Job is suspended
        M="PENDING",  # Job was moved to another server
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

    def _get_states_tabular(self, ssh_client, job_names):
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

        return Pbspro._parse_qstat_tabular(output) if exit_code == 0 else {}

    @staticmethod
    def _parse_qstat_tabular(qstat_output):
        """ Parse two colums `qstat` entries into a dict """

        def parse_qstat_record(record):
            name, state_code = list(map(str.strip, record.split('|')))
            return name, Pbspro._job_states[state_code]

        jobs = qstat_output.splitlines()
        parsed = {}
        # @TODO: think of catch-and-log parsing exceptions
        if jobs and (len(jobs) > 1 or jobs[0] != ''):
            parsed = dict(list(map(parse_qstat_record, jobs)))

        return parsed


def execute_ssh_command(command, workdir, ssh_client, logger):
    _, exit_code = ssh_client.execute_shell_command(command, workdir=workdir, wait_result=True)
    if exit_code != 0:
        logger.error("failed to execute command '" + command + "', exit code " + str(exit_code))
        return False
    return True


def getHours(cput):
    return int(cput[:cput.index(':')])


def getMinutes(cput):
    return int(cput[cput.index(':') + 1:cput.rindex(':')])


def getSeconds(cput):
    return int(cput[cput.rindex(':') + 1:])


def convert_to_seconds(cput):
    hours = getHours(cput)*3600 + getMinutes(cput) * 60.0 + getSeconds(cput)
    return hours


def remove_trailing_unit(value, unit):
    return value[:value.index(unit)]
