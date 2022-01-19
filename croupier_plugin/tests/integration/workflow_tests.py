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


class TestPlugin(unittest.TestCase):
    """ Test workflows class """

    def load_inputs(self, *args, **kwargs):
        """ Parse inputs yaml file """
        if args:
            folder = ''.join(args)
            path = os.path.join('croupier_plugin', 'tests', 'integration', 'blueprints', folder, 'inputs.yaml')
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
    def run_test(self, cfy_local, revoke_vault_token=False, recurring=False):
        if revoke_vault_token:
            cfy_local.execute('croupier_install', task_retries=0)
        else:
            cfy_local.execute('install', task_retries=0)
        if recurring:
            cfy_local.execute('croupier_configure', task_retries=0)
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

    # -------------------------------------------------------------------------------
    # ---------------------------------- Bernoulli ----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'bernoulli', 'blueprint_bernoulli.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'create_bernoulli_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'bernoulli', 'scripts', 'delete_bernoulli_script.sh'), 'scripts')
        ],
        inputs='load_inputs')
    def test_bernoulli(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ----------------------------------- Single ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_single(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------ Single No Vault --------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'no-vault.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='single')
    def test_single_no_vault(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- Single Script ---------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_single_script.yaml'),
        resources_to_copy=[
            (os.path.join('blueprints', 'single', 'scripts', 'create_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'single', 'scripts', 'delete_script.sh'), 'scripts')
        ],
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_single_script(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------- Single Shell Script ------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_single_shell_script.yaml'),
        resources_to_copy=[
            (os.path.join('blueprints', 'single', 'scripts', 'execute.sh'), 'scripts')
        ],
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_single_shell_script(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------ Single Scale -----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_scale.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_single_scale(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- Reservation -----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'reservation', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='reservation')
    def test_reservation(self, cfy_local):
        self.run_test(cfy_local)

    # ------------------------------------------------------------------------------
    # ---------------------------------- Four --------------------------------------
    # ------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'four', 'blueprint_four.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'four', 'scripts', 'create_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'four', 'scripts', 'delete_script.sh'), 'scripts')
        ],
        inputs='load_inputs')
    def test_four(self, cfy_local):
        self.run_test(cfy_local)

    # ------------------------------------------------------------------------------
    # --------------------------------- Four Scale ---------------------------------
    # ------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'four', 'blueprint_four_scale.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[
            (os.path.join('blueprints', 'four', 'scripts', 'create_script.sh'), 'scripts'),
            (os.path.join('blueprints', 'four', 'scripts', 'delete_script.sh'), 'scripts')
        ],
        inputs='load_inputs')
    def test_four_scale(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- MultiHPC -----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'multihpc', 'blueprint_multihpc.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='multihpc')
    def test_multihpc(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- PyCOMPSs -----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'pycompss', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='pycompss')
    def test_pycompss(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- MultiHPC-DM -----------------------------------
    # -------------------------------------------------------------------------------

    @workflow_test(
        os.path.join('blueprints', 'multihpc-dm', 'blueprint_multihpc_dm.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='multihpc-dm')
    def test_multihpc_dm(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- GridFTP-DM -----------------------------------
    # -------------------------------------------------------------------------------

    @workflow_test(
        os.path.join('blueprints', 'gridftp', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='gridftp')
    def test_gridftp_dm(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ----------------------------- MultiHPC Exporter -------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'multihpc', 'blueprint_multihpc_exporter.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_multihpc_exporter(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- HPC Exporter ----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'hpc-exporter', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_exporter(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- Publish ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'publish', 'blueprint_publish.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_publish(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------- Singularity -----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'singularity', 'blueprint_singularity.yaml'),
        copy_plugin_yaml=True,
        resources_to_copy=[(os.path.join('blueprints', 'singularity', 'scripts', 'singularity_bootstrap.sh'),
                            'scripts'),
                           (os.path.join('blueprints', 'singularity', 'scripts', 'singularity_revert.sh'),
                            'scripts')],
        inputs='load_inputs')
    def test_singularity(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # -------------------------------- Openstack ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'openstack', 'blueprint_openstack.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_openstack(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ------------------------------ Openstack HPC ----------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'openstack', 'blueprint_hpc_openstack.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_openstack_hpc(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # ---------------------------------- ECMWF --------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'ecmwf', 'blueprint_ecmwf.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='ecmwf')
    def test_ecmwf(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # -------------------------------- ITAINNOVA ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'itainnova', 'blueprint.yaml'),
        resources_to_copy=[(os.path.join('blueprints', 'itainnova', 'scripts', 'bootstrap.sh'), 'scripts')],
        copy_plugin_yaml=True,
        inputs='load_inputs', input_func_args='itainnova')
    def test_itainnova(self, cfy_local):
        self.run_test(cfy_local)

    # -------------------------------------------------------------------------------
    # -------------------------------- RECURRING ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'single', 'blueprint_recurring.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_recurring(self, cfy_local):
        self.run_test(cfy_local, recurring=True)

    # -------------------------------------------------------------------------------
    # --------------------------------- THREDDS- ------------------------------------
    # -------------------------------------------------------------------------------
    @workflow_test(
        os.path.join('blueprints', 'thredds', 'blueprint.yaml'),
        copy_plugin_yaml=True,
        inputs='load_inputs')
    def test_thredds(self, cfy_local):
        self.run_test(cfy_local, recurring=True)


if __name__ == '__main__':
    unittest.main()
