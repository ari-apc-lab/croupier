.. 
  |Copyright (c) 2019 Atos Spain SA. All rights reserved.
  |
  |This file is part of Croupier.
  |
  |Croupier is free software: you can redistribute it and/or modify it
  |under the terms of the Apache License, Version 2.0 (the License) License.
  |
  |THE SOFTWARE IS PROVIDED "AS IS", WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
  |IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  |FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT, IN NO EVENT SHALL THE
  |AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  |LIABILITY, WHETHER IN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
  |OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  |SOFTWARE.
  |
  |See README file for full disclaimer information and LICENSE file for full
  |license information in the project root.
  |
  |@author: Javier Carnero
  |         Atos Research & Innovation, Atos Spain S.A.
  |         e-mail: javier.carnero@atos.net
  |
  |tosca.rst


.. _modelling:

=========
Modelling
=========

Application run by Cloudify/Croupier must be defined in a TOSCA file(s) - *The Blueprint*. A blueprint is typically composed by a *header*, an *inputs* section, a *node_templates* section, and an outputs section. Optinally can have a *node_types* section.

   **Tip**

   Example blueprints can be found at the `Croupier resources repository <https://github.com/ari-apc-lab/croupier-resources>`__.


.. _header:

Header
------

The header include the TOSCA version used and other imports. In Croupier the Cloudify 1.1.3 tosca version, built-in types and the croupier are mandatory:

.. code:: yaml

   tosca_definitions_version: cloudify_dsl_1_3

   imports:
      # to speed things up, it is possible to download this file,
      - http://raw.githubusercontent.com/ari-apc-lab/croupier/master/resources/types/cfy_types.yaml
      # Croupier pluging
      - http://raw.githubusercontent.com/ari-apc-lab/croupier/master/plugin.yaml
      # Openstack plugin (Optional)
      - http://www.getcloudify.org/spec/openstack-plugin/2.9.0/plugin.yaml
      # The blueprint can be composed by multiple files, in this case we split the inputs section (Optional)
      - inputs-def.yaml

Other TOSCA files can also be imported in the ``inports`` list to compose a blueprint made of more than one file. See `Advanced: Node Types <#node-types>`__ for more info.

.. _inputs:

Inputs
------

In this section is where it is defined all the inputs that the blueprint need. These then can be passed as an argument list in the CLI, or prefereably by an inputs file. An input can define a default value. (See the `CLI docs <https://github.com/ari-apc-lab/croupier-cli/README.md>`__ and the files *inputs-def* and  *local-blueprint-inputs-example.yaml* in the `examples <https://github.com/ari-apc-lab/croupier-resources/examples/inputs>`__).

.. code:: yaml

   inputs:
      hpc_base_dir:
         description: HPC working directory
         default: $HOME

      partition_name:
         default: thinnodes


In the example above, two inputs are defined:

-  ``hpc_base_dir`` as the base working directory, $HOME by default.

-  ``partition_name`` as the partition to be used in an HPC, _thinnodes_ by default.

..

.. _node_templates:

Node Templates
--------------

In the ``node_templates`` section is where your application is actually defined, by stablishing *nodes* and *relations* between them.

To begin with, every *node* is identified by its name (``hpc_wm`` in the example below), and a type is assigned to it.

**Workload Manager example.**

.. code:: yaml

   node_templates:
      hpc_wm:
         type: croupier.nodes.WorkloadManager
         properties:
            config: { get_input: hpc_wm_config }
            credentials: { get_input: hpc_wm_credentials }
            job_prefix: { get_input: job_prefix }
            base_dir: { get_input: "hpc_base_dir" }
            monitor_period: 15
            workdir_prefix: "single_sbatch"

The example above represents a workload manager, with type `croupier.nodes.WorkloadManager`. All computing infrastructures must have a workload manager defined (_Slurm_ or _Torque_ for HPC supported, _BASH_ for Cloud VMs). Then the WM is configured using the inputs (using fuction `get_input`). Detailed information about how to configure the HPCs is in the `Plugin specification <./plugin.html>`__ section. 

The following code uses ``hpc_wm`` to describe four jobs that should run in the hpc that represents the node. Two of them are of type ``croupier.nodes.SingularityJob`` which means that the job will run using a `Singularity <https://singularity.lbl.gov/>`__ container, while the other two of type `croupier.nodes.Job` describe jobs that are going to run directly in the HPC. Navigate to `Cloudify HPC plugin types <./plugin.html#types>`__ to know more about each parameter.

**Four jobs example.**

.. code:: yaml

   first_job:
      type: croupier.nodes.Job
      properties:
         job_options:
            type: 'SBATCH'
            command: "touch.script fourth_example_1.test"
            scale: 4
         deployment:
            bootstrap: 'scripts/bootstrap_sbatch_example.sh'
            revert: 'scripts/revert_sbatch_example.sh'
            inputs:
               - 'first_job'
               - { get_input: partition_name }
      relationships:
         - type: job_managed_by_wm
           target: hpc_wm

   second_parallel_job:
      type: croupier.nodes.SingularityJob
      properties:
         job_options:
            pre:
               - { get_input: mpi_load_command }
               - { get_input: singularity_load_command }
            partition: { get_input: partition_name }
            image: {concat: [{ get_input: singularity_image_storage },'/',{ get_input: singularity_image_filename }] }
            volumes:
               - { get_input: scratch_voulume_mount_point }
            command: 'touch fourth_example_2.test'
            nodes: 1
            tasks: 1
            tasks_per_node: 1
            max_time: '00:01:00'
            scale: 2
         deployment:
            bootstrap: 'scripts/singularity_bootstrap_example.sh'
            revert: 'scripts/singularity_revert_example.sh'
            inputs:
               - { get_input: singularity_image_storage }
               - { get_input: singularity_image_filename }
               - { get_input: singularity_image_uri }
      relationships:
         - type: job_managed_by_wm
           target: hpc_wm
         - type: job_depends_on
           target: first_job
   
   third_parallel_job:
      type: croupier.nodes.SingularityJob
      properties:
         job_options:
            pre:
               - { get_input: mpi_load_command }
               - { get_input: singularity_load_command }
            partition: { get_input: partition_name }
            image: {concat: [{ get_input: singularity_image_storage },'/',{ get_input: singularity_image_filename }] }
            volumes:
               - { get_input: scratch_voulume_mount_point }
            command: 'touch fourth_example_3.test'
            nodes: 1
            tasks: 1
            tasks_per_node: 1
            max_time: '00:01:00'
            scale: 2
         deployment:
               bootstrap: 'scripts/singularity_bootstrap_example.sh'
               revert: 'scripts/singularity_revert_example.sh'
               inputs:
                  - { get_input: singularity_image_storage }
                  - { get_input: singularity_image_filename }
                  - { get_input: singularity_image_uri }
      relationships:
         - type: job_managed_by_wm
           target: hpc_wm
         - type: job_depends_on
           target: first_job

   fourth_job:
      type: croupier.nodes.Job
      properties:
         job_options:
            type: 'SBATCH'
            command: "touch.script fourth_example_4.test"
            scale: 4
         deployment:
            bootstrap: 'scripts/bootstrap_sbatch_example.sh'
            revert: 'scripts/revert_sbatch_example.sh'
            inputs:
               - 'fourth_job'
               - { get_input: partition_name }
         skip_cleanup: True
      relationships:
         - type: job_managed_by_wm
           target: hpc_wm
         - type: job_depends_on
           target: second_parallel_job
         - type: job_depends_on
           target: third_parallel_job


Finally, jobs have two main types of relationships: **job_managed_by_wm**, to stablish which workload manager will run the job, and **job_depends_on**, to describe the dependency between jobs. In the example above, `fourth_job` depends on `three_parallel_job` and `second_parallel_job`, so it will not execute until the other two have finished. In the same way, `three_parallel_job` and `second_parallel_job` depends on `first_job`, so they will run in parallel once the first job is finished. All jobs are contained in `hpc_wm`, so they will run on the HPC using the credentials provided. A third one, **wm_contained_in** is used to link the Workload manager to other Cloudify plugins, sush as Openstack. See `relationships <./plugin.html#relationships>`__ for more information.


.. _outputs:

Outputs
-------

The last section, ``outputs``, helps to publish different attributes of each *node* that can be retrieved after the install workflow of the blueprint has finished (See `Execution <#Execution>`__).

Each output has a name, a description, and value.

.. code:: yaml

   outputs:
      first_job_name:
         description: first job name
         value: { get_attribute: [first_job, job_name] }
      second_job_name:
         description: second job name
         value: { get_attribute: [second_parallel_job, job_name] }
      third_job_name:
         description: third job name
         value: { get_attribute: [third_parallel_job, job_name] }
      fourth_job_name:
         description: fourth job name
         value: { get_attribute: [fourth_job, job_name] }

.. _node-types:

Advanced: Node Types
--------------------

Similarly to how `node_templates` are defined, new node types can be defined to be used as types. Usually these types are going to be defined in a separate file and imported in the blueprint through the `import` keyword in the `header <#header>`__ section, although they can be in the same file.

**Framework example.**

.. code:: yaml

   node_types:
      croupier.nodes.fenics_iter:
         derived_from: croupier.nodes.job
         properties:
            iter_number:
               description: Iteration index (two digits string)
            job_options:
               default:
                  type: 'SBATCH'
                  modules:
                     - 'gcc/5.3.0'
                     - 'impi'
                     - 'petsc'
                     - 'parmetis'
                     - 'zlib'
                  command: { concat: ['/mnt/lustre/scratch/home/otras/ari/jci/wing_minimal/fenics-hpc_hpfem/unicorn-minimal/nautilus/fenics_iter.script ', ' ', { get_property: [SELF, iter_number] }] }

      croupier.nodes.fenics_post:
         derived_from: croupier.nodes.job
         properties:
            iter_number:
                  description: Iteration index (two digits string)
            file:
                  description: Input file for dolfin-post postprocessing
            job_options:
                  default:
                     type: 'SBATCH'
                     modules:
                        - 'gcc/5.3.0'
                        - 'impi'
                        - 'petsc'
                        - 'parmetis'
                        - 'zlib'
                     command: { concat: ['/mnt/lustre/scratch/home/otras/ari/jci/wing_minimal/fenics-hpc_hpfem/unicorn-minimal/nautilus/post.script ', { get_property: [SELF, iter_number] }, ' ', { get_property: [SELF, file] }] }

Above there is dummy example of two new types of the FEniCS framework, derived from ``croupier.nodes.Job``.

The first type, ``croupier.nodes.fenics_iter``, simulates an iteration of the FEniCS framework. A new property has been defined, ``iter_number``, with a description and no default value (so it is mandatory). Besides the ``job_options`` property default value has been overriden with a concrete list of modules, job type, and a command.

The second type, ``croupier.nodes.fenics_post``, described a simulated postprocessing operation of FEniCS, defining again the ``iter_number`` property and another one ``file``. Finally the job options default value has been overriden with a list of modules, a SBATCH type, and a command.

   **Note**

   The commands are built using the functions ``concat`` and ``get_property``. This allows the orchestrator to compose the command based on other properties. See Cloudify intrinsic functions available for more information.

.. _execution:

Execution
---------

Execution of an application is performed through the `CLI docs <https://github.com/ari-apc-lab/croupier-cli/README.md>`__ in your local machine or a host of your own.

.. __steps:

Steps
-----

1. **Upload the blueprint**

   Before doing anything, the blueprint we want to execute needs to be uploaded in the orchestrator with an assigned name.

   ``cfy blueprints upload -b [BLUEPRINT-NAME] [BLUEPRINT-FILE].yaml``

2. **Create a deployment**

   Once we have a blueprint installed, we create a *deployment*, which is a blueprint with an input file attached. This is usefull to have the same blueprint that represents the application, with different configurations (*deployments*). A name has to be assigned to it as well.

   ``cfy deployments create -b [BLUEPRINT-NAME] -i [INPUTS-FILE].yaml --skip-plugins-validation [DEPLOYMENT-NAME]``

      **Note**

      ``--skip-plugins-validation`` is mandatory as we want that the orchestrator download the plugin from a source location (GitHub in our case). This is for testing purposes, and will be removed in future releases.

3. **Install a deployment**

   Install workflow puts everything in place to run the application. Usual tasks in this workflow are data movements, binary downloads, HPC configuration, etc.

   ``cfy executions start -d [DEPLOYMENT-NAME] install``

4. **Run the application**

   Finally to start the execution we run the ``run_jobs`` workflow to start sending jobs to the different infrastructures. The execution can be followed in the output.

   ``cfy executions start -d [DEPLOYMENT-NAME] run_jobs``

      **Note**

      The CLI has a timeout of 900 seconds, which normally is not enough time for an application to finish. However, if the CLI timeout, the execution will still be running on the MSOOrchestrator. To follow the execution just follow the instructions in the output.

.. __revert_previous_steps:

Revert previous Steps
~~~~~~~~~~~~~~~~~~~~~

The following revert the steps above, in order to uninstall the application, recreate the deployment with new inputs, or remove the blueprint (and possibly upload an updated one), follow the following steps.

1. **Uninstall a deployment**

   On the contraty of the *install* workflow, in this case the orchestrator is tipically goint to perform the revert operation of *install*, by deleting execution files or moving data to an external location.

   ``cfy executions start -d [DEPLOYMENT-NAME] uninstall -p ignore_failure=true``

      **Note**

      The ``ignore_failure`` parameter is optional, to perform the *uninstall* even if an error occurs.

2. **Remove a deployment**

   ``cfy deployments delete [DEPLOYMENT-NAME]``

3. **Remove a blueprint**

   ``cfy blueprints delete [BLUEPRINT-NAME]``

.. __troubleshooting:

Troubleshooting
~~~~~~~~~~~~~~~

If an error occurs the revert steps can be followed revert the last steps made. However there are sometimes when the execution is stucked, or you want simply to cancel a runnin execution, or clear a blueprint or deployment that can be uninstall for whatever the reason. The following commands help you resolve these kind of situations.

1. **See executions list and status**

   ``cfy executions list``

2. **Check one execution status**

   ``cfy executions get [EXECUTION-ID]``

3. **Cancel a running (started) execution**

   ``cfy executions cancel [EXECUTION-ID]``

4. **Hard remove a deployment with all its executions and living nodes**

   ``cfy deployments delete [DEPLOYMENT-NAME] -f``

..

   **Tip**
