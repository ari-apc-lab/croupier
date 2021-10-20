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

slurm_tests.py: Holds the Slurm unit tests
"""

from builtins import range
import logging
import unittest

from croupier_plugin.infrastructure_interfaces.infrastructure_interface import (
    InfrastructureInterface)


class TestSlurm(unittest.TestCase):
    """ Holds slurm tests """

    def __init__(self, methodName='runTest'):
        super(TestSlurm, self).__init__(methodName)
        self.wm = InfrastructureInterface.factory("SLURM", False)
        self.logger = logging.getLogger('TestSlurm')

    def test_bad_name(self):
        """ Bad name type. """
        response = self.wm._build_job_submission_call(
            42,
            {'script': 'cmd'})
        self.assertIn('error', response)

    def test_empty_settings(self):
        """ Empty job settings """
        response = self.wm._build_job_submission_call('test', {})
        self.assertIn('error', response)

    def test_basic_sbatch_call(self):
        """ Basic sbatch command. """
        response = self.wm._build_job_submission_call('test',
                                                      {'script': 'cmd'})
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(call, "sbatch --parsable -J 'test' " +
                               "-e test.err -o test.out cmd; ")

    def test_basic_sbatch_call_with_args(self):
        """ Basic sbatch call with args """
        response = self.wm._build_job_submission_call(
            'test',
            {'script': 'cmd',
             'arguments': ['script']})
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            "sbatch --parsable -J 'test' " +
            "-e test.err -o test.out cmd script; ")

    def test_complete_sbatch_call(self):
        """ Complete sbatch command. """
        response = self.wm._build_job_submission_call(
            'test',
            {'pre': [
                'module load mod1',
                './some_script.sh'],
             'script': 'cmd',
             'stderr_file':
             'stderr.out',
             'stdout_file':
             'stdout.out',
             'partition':
             'thinnodes',
             'nodes': 4,
             'tasks': 96,
             'tasks_per_node': 24,
             'memory': '4GB',
             'qos': 'qos',
             'reservation':
                'croupier',
             'mail_user':
             'user@email.com',
             'mail_type': 'ALL',
             'max_time': '00:05:00',
             'post': [
                './cleanup1.sh',
                './cleanup2.sh']})
        self.assertNotIn('error', response)
        self.assertIn('call', response)

        call = response['call']
        self.assertEqual(
            call,
            "module load mod1; ./some_script.sh; "
            "sbatch --parsable -J 'test'"
            " -N 4"
            " -n 96"
            " --ntasks-per-node=24"
            " -t 00:05:00"
            " -p thinnodes"
            " --mem=4GB"
            " --reservation=croupier"
            " --qos=qos"
            " --mail-user=user@email.com"
            " --mail-type=ALL"
            " -e stderr.out"
            " -o stdout.out"
            " cmd; "
            "./cleanup1.sh; ./cleanup2.sh; ")

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

    def test_parse_jobid(self):
        """ Parse JobID from sacct """
        parsed = self.wm._parse_states("test1|012345\n"
                                       "test2|123456\n"
                                       "test3|234567\n",
                                       None)

        self.assertDictEqual(parsed, {'test1': '012345',
                                      'test2': '123456',
                                      'test3': '234567'})

    def test_parse_clean_sacct(self):
        """ Parse no output from sacct """
        parsed = self.wm._parse_states("\n", None)

        self.assertDictEqual(parsed, {})


if __name__ == '__main__':
    unittest.main()
