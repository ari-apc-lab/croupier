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
from croupier_plugin.infrastructure_interfaces.slurm import start_time_tostr, get_job_metrics, _parse_states
from croupier_plugin.ssh import SshClient


class Pycompss(InfrastructureInterface):
    def _get_jobid(self, output):
        return output.split(' ')[-1].strip()

    def _parse_job_settings(
            self,
            job_id,
            job_settings,
            script=False,
            timezone=None):
        """
            Generates Manager specific job submission script/call
            Invoked by InfrastructureInterface at:
                _build_script: to create a Manager specific job submission script content
                    This is only invoked when job submission script content needs to be generated
                    from job specification in workflow. Other alternatives supported by Infrastructure interface
                    includes:
                        a) using a remote script,
                        b) an script content given with the job specification in workflow
                        c) an script file given as resource within the workflow zip
                _build_job_submission_call: to create a Manager specific job submission call
                    job_settings include the name of the script to create for "script" key
                    and additional arguments to pass to the job submission script
                    In caller, job submission script will be enclosed by prefixes and sufixes
                    given in job specification
            @type job_id: string
            @param job_id: name of the job
            @type job_settings: dictionary
            @param job_settings: dictionary with the job options
            @script
            @timezone
            @return dict with two keys:
             'data' parsed data with its parameters, and
             'error' if an error arise.
            """
        pass

    def _build_job_cancellation_call(self, name, job_settings):
        """
        Creates the job cancellation command
        """
        return "scancel --name " + name

    def _get_envar(
            self,
            envar,
            default):
        if envar == 'SCALE_INDEX':
            return '$SLURM_ARRAY_TASK_ID'
        elif envar == 'SCALE_COUNT':
            return '$SLURM_ARRAY_TASK_COUNT'
        else:
            return default

    def get_states(self, ssh_config, job_names):
        """
        Uses Monitoring-enabled Manager for getting job state and accounting audits
        Slurm by default (for PYCOMPSs), given the job submission id
        """
        monitor_start_time_str = start_time_tostr(self.monitor_start_time)
        call = "sacct -n -o JobName,State -X -P --name=" + ','.join(job_names) + " -S " + monitor_start_time_str
        client = SshClient(ssh_config)
        output, exit_code = client.execute_shell_command(
            call,
            workdir=self.workdir,
            wait_result=True)
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

    def delete_reservation(self, ssh_client, reservation_id, deletion_path):
        """
        Manage the deletion of a reservation (if supported with PYCOMPSs, using
        SLURM by default, given the reservation id
        """
        call = 'sudo {0} {1}'.format(deletion_path, reservation_id)
        output, exit_code = ssh_client.execute_shell_command(
            call,
            wait_result=True)
        if exit_code == 0:
            return True
        else:
            return False

    def _add_audit(self, job_id, job_settings, script=False, ssh_client=None):
        # Not supported
        pass
