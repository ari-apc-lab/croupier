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

torque_tests.py: Holds the Torque unit tests
'''

from builtins import map
from builtins import range
from builtins import object
import unittest

import logging
from croupier_plugin.utilities import shlex_quote
from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (
    InfrastructureInterface)


class TestTorque(unittest.TestCase):
    """ Holds Torque tests. """

    def __init__(self, methodName='runTest'):
        super(TestTorque, self).__init__(methodName)
        self.wm = InfrastructureInterface.factory("TORQUE", False)
        self.logger = logging.getLogger('TestTorque')

    def test_bad_name(self):
        """ Bad name type. """
        response = self.wm._build_job_submission_call(
            42,
            {'script': 'cmd'})
        self.assertIn('error', response)

    def test_empty_settings(self):
        """ Empty job settings. """
        response = self.wm._build_job_submission_call('test', {})
        self.assertIn('error', response)

    def test_basic_batch_call(self):
        """ Basic batch call. """
        response = self.wm._build_job_submission_call(
            'test',
            {'script': 'cmd'})
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            "qsub -V -N test -e test.err -o test.out cmd; ")

    def test_basic_batch_call_with_args(self):
        """ Basic batch call with args """
        response = self.wm._build_job_submission_call(
            'test',
            {'script': 'cmd',
             'arguments': ['script']})
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            'qsub -V -N test -e test.err -o test.out cmd -F "script "; ')

    def test_complete_batch_call(self):
        """ Complete batch call. """
        response = self.wm._build_job_submission_call(
            'test',
            dict(pre=[
                'module load mod1',
                './some_script.sh'],
                type='BATCH',
                script='cmd',
                partition='thinnodes',
                nodes=4,
                tasks=96,
                tasks_per_node=24,
                max_time='00:05:00',
                post=[
                './cleanup1.sh',
                './cleanup2.sh']))
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            "module load mod1; ./some_script.sh; "
            "qsub -V"
            " -N test"
            " -l nodes=4:ppn=24"
            " -l walltime=00:05:00"
            " -q thinnodes"
            " -e test.err -o test.out"
            " cmd; "
            "./cleanup1.sh; ./cleanup2.sh; ")

    def test_batch_call_with_job_array(self):
        """ Complete batch array call. """
        response = self.wm._build_job_submission_call(
            'test',
            dict(pre=[
                'module load mod1',
                './some_script.sh'],
                script='cmd',
                partition='thinnodes',
                nodes=4,
                tasks=96,
                tasks_per_node=24,
                max_time='00:05:00',
                scale=10,
                scale_max_in_parallel=2,
                post=[
                './cleanup1.sh',
                './cleanup2.sh']))
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            "module load mod1; ./some_script.sh; "
            "qsub -V"
            " -N test"
            " -l nodes=4:ppn=24"
            " -l walltime=00:05:00"
            " -q thinnodes"
            " -e test.err -o test.out"
            " -t 0-9%2"
            " cmd; "
            "./cleanup1.sh; ./cleanup2.sh; ")
        scale_env_mapping_call = response['scale_env_mapping_call']
        self.assertEqual(scale_env_mapping_call,
                         "sed -i '/# DYNAMIC VARIABLES/a\\"
                         "SCALE_INDEX=$PBS_ARRAYID\\n"
                         "SCALE_COUNT=10\\n"
                         "SCALE_MAX=2' cmd")

    def test_cancellation_call(self):
        """ Jobs cancellation call. """
        response = self.wm._build_job_cancellation_call('test',
                                                        {},
                                                        self.logger)
        self.assertEqual(response, "qdel")

    @unittest.skip("deprecated")
    def test_identifying_job_ids_call(self):
        """ Call for revealing job ids by job names. """
        job_names = ('test_1', 'test 2')

        # @TODO: replace by _get_jobids_by_name() as soon as the dependency on
        #        SSH client is removed.
        from croupier_plugin.utilities import shlex_quote
        response = "qstat -i `echo {} | xargs -n 1 qselect -N` |"\
                   " tail -n+6 | awk '{{ print $4 \" \" $1 }}'".format(
                       shlex_quote(' '.join(map(shlex_quote, job_names))))

        self.assertEqual(response, 'qstat -i '
                         '`echo \'\'"\'"\'test 2\'"\'"\' test_1\' |'
                         ' xargs -n 1 qselect -N` |'
                         ' tail -n+6 | awk \'{ print $4 " " $1 }\'')

    @unittest.skip("deprecated")
    def test_identifying_job_status_call(self):
        """ Call for revealing status of jobs by job ids. """
        job_ids = {'1.some.host', '11.some.host'}

        # @TODO: replace by _get_jobids_by_name() as soon as the dependency on
        #        SSH client is removed.
        response = "qstat -i {} | tail -n+6 | awk '{{ print $1 \" \" $10 }}'".\
            format(' '.join(job_ids))

        self.assertEqual(
            response, 'qstat -i 11.some.host 1.some.host |'
            ' tail -n+6 | awk \'{ print $1 " " $10 }\'')

    def test_get_states(self):
        """ Call for revealing job ids by job names. """
        # from croupier_plugin.cli_client.cli_client import ICliClient

        job_names = ('test_1', 'test 2')

        class MockClient(object):
            def __init__(self, test_case):
                self._test_case = test_case

            def is_open(self):
                return True

            def send_command(self, command, **kwargs):
                expected_cmd = 'qstat -i'\
                               ' `echo {} '\
                               '| xargs -n 1 qselect -N` '\
                               '| tail -n+6 '\
                               '| awk \'{{ print $4 "|" $10 }}\''.format(
                                   shlex_quote(' '.join(
                                       map(shlex_quote, job_names))))
                self._test_case.assertEqual(command, expected_cmd)
                return """   test_1 | S
   test 2   | R\n""", 0

        response = self.wm._get_states_tabular(
            MockClient(self), job_names, self.logger)
        self.assertDictEqual(
            response, {'test_1': 'SUSPENDED', 'test 2': 'RUNNING'})

    def test_random_name(self):
        """ Random name formation. """
        name = self.wm._get_random_name('base')

        self.assertEqual(11, len(name))
        self.assertEqual('base_', name[:5])

    def test_random_name_uniqueness(self):
        """ Random name uniqueness. """
        names = []
        for _ in range(0, 50):
            names.append(self.wm._get_random_name('base'))

        self.assertEqual(len(names), len(set(names)))


if __name__ == '__main__':
    unittest.main()
