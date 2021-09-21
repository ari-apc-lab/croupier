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
@author: Jesus Gorronogoitia
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: jesus.gorronogoitia@atos.net
workflow_tests.py
"""

from __future__ import print_function

import logging
import os
import unittest
import errno
import yaml
from cloudify.test_utils import workflow_test


def _load_inputs(inputs_file, *args, **kwargs):
    """ Parse inputs yaml file """
    # Check whether a inputs_file file is available
    if not os.path.isfile(inputs_file):
        raise IOError(
            errno.ENOENT, os.strerror(errno.ENOENT), inputs_file)
    inputs = {}
    print(("Using inputs file:", inputs_file))
    with open(os.path.join(inputs_file),
              'r') as stream:
        try:
            inputs = yaml.full_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    return inputs


class TestPlugin(unittest.TestCase):
    """ Test workflows class """

    def set_inputs(self, *args, **kwargs):  # pylint: disable=W0613
        """ Parse inputs yaml file """
        # Check whether a local inputs file is available
        inputs_file = 'blueprint-inputs.yaml'
        if os.path.isfile(os.path.join('croupier_plugin', 'tests', 'integration', 'inputs', 'local-blueprint-inputs'
                                                                                            '.yaml')):
            inputs_file = 'local-blueprint-inputs.yaml'
        inputs = {}
        print("Using inputs file:", inputs_file)
        with open(os.path.join('croupier_plugin', 'tests', 'integration', 'inputs', inputs_file), 'r') as stream:
            try:
                inputs = yaml.full_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

        return inputs

    def load_inputs(self, inputs_file, *args, **kwargs):
        """ Parse inputs yaml file """
        # Check whether a inputs_file file is available
        if not os.path.isfile(os.path.join('croupier_plugin', 'tests', 'integration', 'inputs', inputs_file)):
            raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), inputs_file)
        inputs = {}
        print ("Using inputs file:" + inputs_file)
        with open(os.path.join('croupier_plugin', 'tests', 'integration', 'inputs', inputs_file), 'r') as stream:
            try:
                inputs = yaml.full_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

        return inputs

    # Run every test
    def run_test(self, cfy_local):
        cfy_local.execute('install', task_retries=0)
        cfy_local.execute('run_jobs', task_retries=0)
        cfy_local.execute('uninstall', task_retries=0)

        # extract single node instance
        instance = cfy_local.storage.get_node_instances()[0]

        # due to a cfy bug sometimes login keyword is not ready in the tests
        if 'login' in instance.runtime_properties:
            # assert runtime properties is properly set in node instance
            self.assertEqual(instance.runtime_properties['login'], True)
        else:
            logging.warning('[WARNING] Login could not be tested')

    @workflow_test(
        os.path.join('blueprints', 'blueprint_single.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='set_inputs')
    def test_single(self, cfy_local):
        """ Single BATCH Job Blueprint """
        self.run_test(cfy_local)

    @workflow_test(
        os.path.join('blueprints', 'blueprint_met_00.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                           (os.path.join('blueprints', 'scripts', 'precip_00.sh'), 'scripts'),
                           (os.path.join('blueprints', 'scripts', 'wind_00.sh'), 'scripts'),
                           (os.path.join('blueprints', 'scripts', 'temp_00.sh'), 'scripts')],
        inputs='set_inputs')
    def test_agroapps_zerozero(self, cfy_local):
        self.run_test(cfy_local)

    @workflow_test(
        os.path.join('blueprints', 'blueprint_single.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='set_inputs')
    def test_single(self, cfy_local):
        """ Single BATCH Job Blueprint """
        self.run_test(cfy_local)

    @workflow_test(
        os.path.join('blueprints', 'blueprint_met_00.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                           (os.path.join('blueprints', 'scripts', 'precip_00.sh'), 'scripts'),
                           (os.path.join('blueprints', 'scripts', 'wind_00.sh'), 'scripts'),
                           (os.path.join('blueprints', 'scripts', 'temp_00.sh'), 'scripts')],
        inputs='set_inputs')
    def test_agroapps_zerozero(self, cfy_local):
        self.run_test(cfy_local)

    @workflow_test(
        os.path.join('blueprints', 'blueprint_grapevine_test.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='set_inputs')
    def test_grapevine(self, cfy_local):
        """ Single BATCH Job Blueprint """
        self.run_test(cfy_local)

    # Singularity easy job in CESGA HPC
    def load_cesga_hpc_singularity_easy_inputs(self, *args, **kwargs):
        return self.load_inputs('easy-singularity-blueprint-inputs.yaml')

    @workflow_test(
        os.path.join('blueprints', 'blueprint_singularity.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'easy-singularity', 'inputs_def.yaml'), './'),
                           (os.path.join('blueprints', 'easy-singularity', 'scripts',
                                         'singularity_bootstrap_example.sh'), 'scripts'),
                           (os.path.join('blueprints', 'easy-singularity', 'scripts',
                                         'singularity_revert_example.sh'), 'scripts')],
        inputs='load_cesga_hpc_singularity_easy_inputs')
    def test_singularity_easy(self, cfy_local):
        """ Singularity Job Blueprint """
        self.run_test(cfy_local)

    # Agroapps test in CESGA HPC
    @workflow_test(
        os.path.join('blueprints', 'blueprint_agroapps_test_GFS_00.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='set_inputs')
    def test_cesga_agroapps(self, cfy_local):
        """ CESGA Agroapps Job Blueprint """
        self.run_test(cfy_local)

    # Easy test in CESGA HPC
    def load_cesga_hpc_inputs(self, *args, **kwargs):
        return self.load_inputs('cesga-blueprint-inputs.yaml')

    @workflow_test(
        os.path.join('blueprints', 'blueprint_easy.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='load_cesga_hpc_inputs')
    def test_easy_job(self, cfy_local):
        """ Single BATCH Job Blueprint """
        self.run_test(cfy_local)

    # Single test in Sodalite HPC
    def load_sodalite_hpc_inputs(self, *args, **kwargs):
        return self.load_inputs('blueprint-sodalite-inputs.yaml')

    @workflow_test(
        os.path.join('blueprints', 'blueprint_single.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
        inputs='load_sodalite_hpc_inputs')
    def test_single_sodalite(self, cfy_local):
        """ Single BATCH Job Blueprint """
        self.run_test(cfy_local)

    def load_bernoulli_inputs(self, *args, **kwargs):
        return _load_inputs(os.path.join('croupier_plugin',
                                         'tests',
                                         'integration',
                                         'blueprints',
                                         'bernoulli',
                                         'cesga-blueprint-inputs.yaml'))

    @workflow_test(
        os.path.join('blueprints', 'bernoulli', 'blueprint_bernoulli.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'create_bernoulli_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'delete_bernoulli_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'bernoulli', 'inputs_def.yaml'), './')
        ],
        inputs='load_bernoulli_inputs')
    def test_bernoulli(self, cfy_local):
        self.run_test(cfy_local)

    @workflow_test(
        os.path.join('blueprints', 'blueprint_singularity.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                           (os.path.join('blueprints', 'scripts', 'singularity_bootstrap_example.sh'), 'scripts'),
                           (os.path.join('blueprints', 'scripts', 'singularity_revert_example.sh'), 'scripts')],
        inputs='set_inputs')
    def test_singularity(self, cfy_local):
        self.run_test(cfy_local)

    # Four job workflow
    def load_four_inputs(self, *args, **kwargs):
        return _load_inputs(os.path.join('croupier_plugin', 'tests', 'integration', 'blueprints', 'four',
                                         'four_inputs.yaml'))

    @workflow_test(os.path.join('blueprints', 'four', 'blueprint_four.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                                      (os.path.join('blueprints', 'scripts', 'create_script.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'delete_script.sh'), 'scripts')],
                   inputs='set_inputs')
    def test_four(self, cfy_local):
        self.run_test(cfy_local)

    @workflow_test(os.path.join('blueprints', 'blueprint_four_singularity.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                                      (os.path.join('blueprints', 'scripts', 'singularity_bootstrap.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'singularity_revert.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'create_script.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'delete_script.sh'), 'scripts')],
                   inputs='set_inputs')
    def test_four_singularity(self, cfy_local):
        """ Four Jobs Blueprint """
        self.run_test(cfy_local)

    @workflow_test(os.path.join('blueprints', 'blueprint_four_scale.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                                      (os.path.join('blueprints', 'scripts', 'create_script.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'delete_script.sh'), 'scripts')],
                   inputs='set_inputs')
    def test_four_scale(self, cfy_local):
        self.run_test(cfy_local)

    # Agroclimate Zones Pilot Test with data mover
    def load_grapevine_cycle_00_spain_inputs(self, *args, **kwargs):
        return self.load_inputs('cycle_00_part2_spain_no_reservation_inputs.yaml')

    @workflow_test(os.path.join('blueprints', 'cycle_00_part2_spain_no_reservation', 'blueprint.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './')],
                   inputs='load_grapevine_cycle_00_spain_inputs')
    def test_grapevine_cycle_00_spain(self, cfy_local):
        self.run_test(cfy_local)

    @workflow_test(os.path.join('blueprints', 'blueprint_eosc.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'inputs_def.yaml'), './'),
                                      (os.path.join('blueprints', 'scripts', 'singularity_bootstrap.sh'), 'scripts'),
                                      (os.path.join('blueprints', 'scripts', 'singularity_revert.sh'), 'scripts')],
                   inputs='set_inputs')
    def test_eosc(self, cfy_local):
        self.run_test(cfy_local)

    def set_inputs_vault(self, *args, **kwargs):
        inputs_filename = os.path.join('croupier_plugin', 'tests', 'integration', 'blueprints', 'vault', 'inputs.yaml')
        if not os.path.isfile(inputs_filename):
            raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), inputs_filename)
        inputs = {}
        print("Using inputs file:" + inputs_filename)
        with open(inputs_filename, 'r') as stream:
            try:
                inputs = yaml.full_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        return inputs

    @workflow_test(os.path.join('blueprints', 'vault', 'blueprint.yaml'),
                   copy_plugin_yaml=True,
                   resources_to_copy=[(os.path.join('blueprints', 'vault', 'inputs_def.yaml'), './')],
                   inputs='set_inputs_vault')
    def test_vault(self, cfy_local):
        self.run_test_vault(cfy_local)


if __name__ == '__main__':
    unittest.main()
