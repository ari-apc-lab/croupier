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
@author: Jesus Ramos Rivas
         Atos Research & Innovation, Atos Spain S.A.
         e-mail: jesus.2.ramos@atos.net

workflow_tests.py
"""

from __future__ import print_function

import logging
import os
import unittest
import errno
import yaml
from cloudify.test_utils import workflow_test


def load_inputs(folder, inputs='inputs.yaml', *args, **kwargs):
    """ Parse inputs yaml file """
    if folder:
        path = os.path.join('croupier_plugin', 'tests', 'integration', 'blueprints', folder, inputs)
    else:
        path = os.path.join('croupier_plugin', 'tests', 'integration', 'inputs.yaml')

    # Check whether a inputs_file file is available
    if not os.path.isfile(path):
        raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), path)
    inputs = {}
    print("Using inputs file:" + path)
    with open(path, 'r') as stream:
        try:
            inputs = yaml.full_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    return inputs


# Run every test
def run_test(test_plugin, cfy_local, revoke_vault_token=False):
    if revoke_vault_token:
        cfy_local.execute('croupier_install', task_retries=0)
    else:
        cfy_local.execute('install', task_retries=0)
    cfy_local.execute('run_jobs', task_retries=0)
    cfy_local.execute('uninstall', task_retries=0)

    # extract single node instance
    instance = cfy_local.storage.get_node_instances()[0]

    # due to a cfy bug sometimes login keyword is not ready in the tests
    if 'login' in instance.runtime_properties:
        # assert runtime properties is properly set in node instance
        test_plugin.assertEqual(instance.runtime_properties['login'], True)
    else:
        logging.warning('[WARNING] Login could not be tested')


class TestPlugin(unittest.TestCase):
    """ Test workflows class """

    # -------------------------------------------------------------------------------
    # ---------------------------------- Bernoulli ----------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_bernoulli(self, *args, **kwargs):
        return load_inputs('bernoulli')

    @workflow_test(
        os.path.join('blueprints', 'bernoulli', 'blueprint_bernoulli.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'create_bernoulli_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'delete_bernoulli_script.sh'), 'scripts')
        ],
        inputs='load_inputs')
    def test_bernoulli(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ----------------------------------- Single ------------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_single(self, *args, **kwargs):
        return load_inputs('single')

    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_single')
    def test_single(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- Single Script ---------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_single_script(self, *args, **kwargs):
        return load_inputs('single')

    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_single_script.yaml'),
        resources_to_copy=[
            (os.path.join('blueprints', 'single', 'scripts', 'create_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'single', 'scripts', 'delete_script.sh'), 'scripts')
        ],
        copy_plugin_yaml=True,
        inputs='load_inputs_single_script')
    def test_single_script(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------ Single Scale -----------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_single_scale(self, *args, **kwargs):
        return load_inputs('single')

    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_scale.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_single_scale')
    def test_single_scale(self, cfy_local):
        run_test(self, cfy_local)

    # ------------------------------------------------------------------------------
    # ------------------------------------ Four ------------------------------------
    # ------------------------------------------------------------------------------
    def load_inputs_four(self, *args, **kwargs):
        return load_inputs('four')

    # @workflow_test(
    #     os.path.join('blueprints', 'four', 'blueprint_four.yaml'),
    #     copy_plugin_yaml=True,
    #     resources_to_copy=[
    #         (os.path.join('blueprints', 'four', 'scripts', 'create_script.sh'), 'scripts'),
    #         (os.path.join('blueprints', 'four', 'scripts', 'delete_script.sh'), 'scripts')
    #     ],
    #     inputs='load_inputs_four')
    # def test_four(self, cfy_local):
    #     run_test(self, cfy_local)

    # ------------------------------------------------------------------------------
    # --------------------------------- Four Scale ---------------------------------
    # ------------------------------------------------------------------------------
    def load_inputs_four_scale(self, *args, **kwargs):
        return load_inputs('four')

    @workflow_test(
        os.path.join('blueprints', 'four', 'blueprint_four_scale.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'four', 'scripts', 'create_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'four', 'scripts', 'delete_script.sh'), 'scripts')
        ],
        inputs='load_inputs_four_scale')
    def test_four_scale(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- MultiHPC -----------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_multihpc(self, *args, **kwargs):
        return load_inputs('multihpc')

    @workflow_test(
        os.path.join('blueprints', 'multihpc', 'blueprint_multihpc.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_multihpc')
    def test_multihpc(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ----------------------------- MultiHPC Exporter -------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_multihpc_exporter(self, *args, **kwargs):
        return load_inputs('multihpc')

    @workflow_test(
        os.path.join('blueprints', 'multihpc', 'blueprint_multihpc_exporter.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_multihpc_exporter', input_func_args='multihpc')
    def test_multihpc_exporter(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- HPC Exporter ----------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_hpc_exporter(self, *args, **kwargs):
        return load_inputs('hpc-exporter')

    @workflow_test(
        os.path.join('blueprints', 'hpc-exporter', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_hpc_exporter')
    def test_hpc_exporter(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- Publish ------------------------------------
    # -------------------------------------------------------------------------------
    # def load_inputs_publish(self, *args, **kwargs):
    #     return load_inputs('publish')
    #
    # @workflow_test(
    #     os.path.join('blueprints', 'publish', 'blueprint_publish.yaml'),
    #     copy_plugin_yaml=True,
    #     inputs='load_inputs_publish')
    # def test_publish(self, cfy_local):
    #    run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- Singularity -----------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_singularity(self, *args, **kwargs):
        return load_inputs('singularity')

    @workflow_test(
        os.path.join('blueprints', 'singularity', 'blueprint_singularity.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'singularity', 'scripts', 'singularity_bootstrap.sh'),
                            'scripts'),
                           (os.path.join('blueprints', 'singularity', 'scripts', 'singularity_revert.sh'),
                            'scripts')],
        inputs='load_inputs_singularity')
    def test_singularity(self, cfy_local):
        run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # -------------------------------- Openstack ------------------------------------
    # -------------------------------------------------------------------------------
    # def load_inputs_openstack(self, *args, **kwargs):
    #     return load_inputs('openstack')
    #
    # @workflow_test(
    #     os.path.join('blueprints', 'openstack', 'blueprint_openstack.yaml'),
    #     copy_plugin_yaml=True,
    #     inputs='load_inputs_openstack')
    # def test_openstack(self, cfy_local):
    #     run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------ Openstack HPC ----------------------------------
    # -------------------------------------------------------------------------------
    # def load_inputs_openstack_hpc(self, *args, **kwargs):
    #     return load_inputs('openstack')
    #
    # @workflow_test(
    #     os.path.join('blueprints', 'openstack', 'blueprint_hpc_openstack.yaml'),
    #     copy_plugin_yaml=True,
    #     inputs='load_inputs_openstack_hpc')
    # def test_openstack_hpc(self, cfy_local):
    #     run_test(self, cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- ECMWF --------------------------------------
    # -------------------------------------------------------------------------------
    def load_inputs_ecmwf(self, *args, **kwargs):
        return load_inputs('ecmwf')

    @workflow_test(
        os.path.join('blueprints', 'ecmwf', 'blueprint_ecmwf.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs_ecmwf', input_func_args='ecmwf')
    def test_ecmwf(self, cfy_local):
        run_test(self, cfy_local)


if __name__ == '__main__':
    unittest.main()
