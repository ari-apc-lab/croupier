..
  |Copyright (c) 2019 Atos Spain SA. All rights reserved.
  |
  |This file is part of Croupier.
  |
  |Croupier is free software: you can redistribute it and/or modify it
  |under the terms of the Apache License, Version 2.0 (the License) License.
  |
  |THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
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
  |plugin.rst


========================
Croupier Cloudify plugin
========================

.. _requirements:

Requirements
-------------------

- Python version
   - 2.7.x

.. _compatibility:

Compatibility
-------------

- `Slurm <https://slurm.schedmd.com/>`__ based HPC by ssh user & key/password.

- `Moab/Torque <http://www.adaptivecomputing.com/products/open-source/torque>`__ based HPC by ssh user & key/password.

- Tested with `Openstack plugin <https://docs.cloudify.co/4.5.5/working_with/official_plugins/openstack>`__.

   **Tip**

   Example blueprints can be found at the `Croupier resources repository <https://github.com/ari-apc-lab/croupier-resources>`__.


.. _configuration:

Configuration
------------------------

The HPC plugin requires credentials, endpoint and other setup
information in order to authenticate and interact with them.

This configuration properties are defined in
`??? <#croupier.nodes.Compute>`__ *credentials* and *config* properties.

.. code:: yaml

   credentials:
       host: "[HPC-HOST]"
       user: "[HPC-SSH-USER]"
       private_key: |
           -----BEGIN RSA PRIVATE KEY-----
           ......
           -----END RSA PRIVATE KEY-----
       private_key_password: "[PRIVATE-KEY-PASSWORD]"
       password: "[HPC-SSH-PASS]"
       login_shell: {true|false}
       tunnel:
           host: ...
           ...

1. HPC and ssh credentials. At least ``private_key`` or ``password``
   must be provided.

   a. *tunnel*: Follows the same structure as its parent (credentials),
      to connect to the HPC through an tunneled SSH connection.

.. code:: yaml

   config:
       country_tz: "Europe/Madrid"
       workload_manager: {"SLURM"|"TORQUE"}

1. *country_tz*: Country Time Zone configured in the the HPC.

2. *workload_manager*: Workload manager used by the HPC.

..

   **Warning**

   Only Slurm and Torque are currently accepted as workload managers.

.. _types:

Types
-----

This section describes the `node
type <http://docs.getcloudify.org/4.1.0/blueprints/spec-node-types/>`__
definitions. Nodes describe resources in your HPC infrastructures. For
more information, see `node
type <http://docs.getcloudify.org/4.1.0/blueprints/spec-node-types/>`__.

.. _hpc_nodes_workloadmanager:

croupier.nodes.WorkloadManager
-------------------------

**Derived From:**
`cloudify.nodes.Compute <http://docs.getcloudify.org/4.1.0/blueprints/built-in-types/>`__

Use this type to describe a HPC infrastructure.

**Properties:**

-  ``credentials``: Connection credentials, as described in
   `??? <#hpc-config-properties>`__.

-  ``config``: HPC configuration, as described in
   `??? <#hpc-config-properties>`__.

-  ``external_monitor_entrypoint``: Entrypoint of the external monitor
   that Cloudify will use instead of the internal one.

-  ``external_monitor_port``: Port of the monitor. Default ``:9090``.

-  ``external_monitor_type``: Specific monitor tool. Default
   ``{uri-prometheus}[PROMETHEUS]``.

-  ``external_monitor_orchestrator_port``: Monitor orchestrator port.
   Default ``:8079``.

-  ``job_prefix``: Job name prefix for the jobs created in this HPC.
   Default ``cfyhpc``.

-  ``base_dir``: Root directory in which to run the executions in this
   ifrastructure. Default ``$HOME``.

-  ``workdir_prefix``: Prefix name of the working directory that will be
   created for this infrastructure.

-  ``monitor_period``: Seconds to check job status. This is necessary
   because workload managers can be overloaded if asked too much times
   in a short period of time. Default ``60``.

-  ``skip_cleanup``: True to not clean all files when destroying the
   deployment. Default ``False``.

-  ``simulate``: If true, don’t send the jobs to the HPC and simulate
   that they finish inmediately. Useful for test new TOSCA files.
   Default ``False``.

**Example**

This example demonstrates how to add a new HPC.

.. code:: yaml

       hpc_wm:
           type: croupier.nodes.WorkloadManager
           properties:
               credentials:
                   host: "[HPC-HOST]"
                   user: "[HPC-SSH-USER]"
                   password: "[HPC-SSH-PASS]"
                   login_shell: false
               config:
                   country_tz: "Europe/Madrid"
                   workload_manager: "SLURM"
               job_prefix: wm_
               workdir_prefix: test
   ...

**Mapped Operations:**

-  ``cloudify.interfaces.lifecycle.configure`` Checks that there is
   connection between Cloudify and the HPC, and creates a new working
   directory.

-  ``cloudify.interfaces.lifecycle.delete`` Clean up all data generated
   by the execution.

-  ``cloudify.interfaces.monitoring.start`` If the external monitor
   orchestrator is available, sends a notification to start monitoring
   the HPC.

-  ``cloudify.interfaces.monitoring.stop`` If the external monitor
   orchestrator is available, sends a notification to end monitoring the
   HPC.

.. _hpc_nodes_job:

croupier.nodes.Job
-------------

Use this tipe to describe a HPC job.

**Properties:**

-  ``job_options``: Job parameters and needed resources.

   -  ``type``: INTERACTIVE or BATCH (job executed using a command or using a
      script). TORQUE supports only BATCH mode.

   -  ``pre``: List of commands to be executed before running the job.
      Optional.

   -  ``post``: List of commands to be executed after running the job.
      Optional.

   -  ``partition``: Partition in which the job will be executed. If not
      provided, the HPC default will be used.

   -  ``command``: Job executable command with arguments if necessary.
      Since TORQUE does NOT accept extra arguments in job submission
      command ``qsub``, this field must contain only a name of the batch
      script to run for TORQUE. Mandatory.

   -  ``nodes``: Necessary nodes of the job. Default ``1``.

   -  ``tasks``: Number of tasks of the job. Default ``1``.

   -  ``tasks_per_node``: Number of tasks per node. Default ``1``.

   -  ``max_time``: Set a limit on the total run time of the job
      allocation. Mandatory if INTERACTIVE type.

   -  ``scale``: Execute in parallel the job N times according to this
      property. Only works with BATCH jobs. Default ``1`` (no scale).

   -  ``scale_max_in_parallel``: Maximum number of scaled job instances
      that can be run in parallel. Only works with scale > ``1``.
      Default same as scale.

   -  ``memory``: Specify the real memory required per node. Different
      units can be specified using the suffix [``K|M|G|T``]. Default
      value ``""`` lets the workload manager assign the default memory
      to the job.

   -  ``stdout_file``: Define the file where to gather the standard
      output of the job. Default value ``""`` sets ``<job-name>.err``
      filename.

   -  ``stderr_file``: Define the file where to gather the standard
      error output. Default value ``""`` sets ``<job-name>.out``
      filename.

   -  ``mail-user``: Email to receive notification of job state changes.
      Default value ``""`` does not send any mail.

   -  ``mail-type``: Type of event to be notified by mail, can define
      several events separated by comma. Valid values
      ``NONE, BEGIN, END, FAIL, TIME_LIMIT, REQUEUE, ALL``. Default
      value ``""`` does not send any mail.

   -  ``reservation``: Allocate resources for the job from the named
      reservation. Default value ``""`` does not allocate from any named
      reservation.

   -  ``qos``: Request a quality of service for the job. Default value
      ``""`` lets de workload manager assign the default user ``qos``.

-  ``deployment``: Scripts to perform deployment operations. Optional.

   -  ``bootstrap``: Relative path to blueprint to the script that will
      be executed in the HPC at the install workflow to bootstrap the
      job (like data movements, binary download, etc.)

   -  ``revert``: Relative path to blueprint to the script that will be
      executed in the HPC at the uninstall workflow, reverting the
      bootstrap or other clean up operations.

   -  ``inputs``: List of inputs that will be passed to the scripts when
      executed in the HPC.

-  ``publish``: A list of outputs to be published after job execution.
   Each list item is a dictionary containing:

   -  ``type``: Type of the external repository to be published. Only
      ``CKAN`` is supported for now. The rest of the parameters depends
      on the type.

   -  ``type: CKAN``

      -  ``entrypoint``: ckan entrypoint

      -  ``api_key``: Individual user ckan api key.

      -  ``dataset``: Id of the dataset in which the file will be
         published.

      -  ``file_path``: Local path of the output file in the computation
         node.

      -  ``name``: Name used to publish the file in the repository.

      -  ``description``: Text describing the data file.

-  ``skip_cleanup``: Set to true to not clean up orchestrator auxiliar
   files. Default ``False``.

..

   **Note**

   The variable $CURRENT_WORKDIR is available in all operations and
   scripts. It points to the working directory of the execution in the
   HPC from the *HOME* directory: ``/home/user/$CURRENT_WORKDIR/``.

   **Note**

   The variables ``$SCALE_INDEX``, ``$SCALE_COUNT`` and ``$SCALE_MAX``
   will be available in the batch script if the line
   ``# DYNAMIC VARIABLES`` exist (they will be dynamicaly loaded after
   this line). They hold, for each job instance, the index, the total
   number of instances, and the maximun in parallel respectively.

**Example**

This example demonstrates how to describe a new job for non-batched run
(in Slurm).

.. code:: yaml

       hpc_job:
           type: croupier.nodes.Job
           properties:
               job_options:
                   type: 'INTERACTIVE'
                   pre:
                       - module load gcc/5.3.0
                   partition: 'thin-shared'
                   command: 'touch example.test'
                   nodes: 1
                   tasks: 1
                   tasks_per_node: 1
                   max_time: '00:01:00'
               deployment:
                   bootstrap: 'scripts/bootstrap_example.sh'
                   revert: 'scripts/revert_example.sh'
                   inputs:
                       - 'example_job'
   ...

This example demonstrates how to describe a new batch job (works with
both Slurm and Torque).

.. code:: yaml

       hpc_batch_job:
           type: croupier.nodes.job
           properties:
               job_options:
                   type: 'BATCH'
                   command: "touch.script"
               deployment:
                   bootstrap: 'scripts/bootstrap_sbatch_example.sh'
                   revert: 'scripts/revert_sbatch_example.sh'
                   inputs:
                       - 'single'
               skip_cleanup: True
           relationships:
               - type: job_contained_in_hpc
                 target: first_hpc
   ...

**Mapped Operations:**

-  ``cloudify.interfaces.lifecycle.start`` Send and execute the
   bootstrap script.

-  ``cloudify.interfaces.lifecycle.stop`` Send and execute the revert
   script.

-  ``croupier.interfaces.lifecycle.queue`` Queues the job in the HPC.

-  ``croupier.interfaces.lifecycle.publish`` Publish outputs outside the HPC.

-  ``croupier.interfaces.lifecycle.cleanup`` Clean up operations after job is
   finished.

-  ``croupier.interfaces.lifecycle.cancel`` Cancels a queued job.

.. _hpc_nodes_singularityjob:

croupier.nodes.SingularityJob
------------------------

**Derived From:** `??? <#croupier.nodes.job>`__

Use this tipe to describe a HPC job executed from a
`Singularity <http://singularity.lbl.gov/>`__ image. Note that in this
version TORQUE does not support Singularity jobs yet.

**Properties:**

-  ``job_options``: Job parameters and needed resources.

   -  ``pre``: List of commands to be executed before running
      singularity container. Optional.

   -  ``post``: List of commands to be executed after running
      singularity container. Optional.

   -  ``image``: `Singularity <http://singularity.lbl.gov/>`__ image
      file.

   -  ``home``: Home volume that will be bind with the image instance
      (Optional).

   -  ``volumes``: List of volumes that will be bind with the image
      instance.

   -  ``partition``: Partition in which the job will be executed. If not
      provided, the HPC default will be used.

   -  ``nodes``: Necessary nodes of the job. 1 by default.

   -  ``tasks``: Number of tasks of the job. 1 by default.

   -  ``tasks_per_node``: Number of tasks per node. 1 by default.

   -  ``max_time``: Set a limit on the total run time of the job
      allocation. Mandatory if INTERACTIVE type.

   -  ``scale``: Execute in parallel the job N times according to this
      property. Default ``1`` (no scale).

   -  ``scale_max_in_parallel``: Maximum number of scaled job instances
      that can be run in parallel. Only works with scale > ``1``.
      Default same as scale.

   -  ``memory``: Specify the real memory required per node. Different
      units can be specified using the suffix [``K|M|G|T``]. Default
      value ``""`` lets the workload manager assign the default memory
      to the job.

   -  ``stdout_file``: Define the file where to gather the standard
      output of the job. Default value ``""`` sets ``<job-name>.err``
      filename.

   -  ``stderr_file``: Define the file where to gather the standard
      error output. Default value ``""`` sets ``<job-name>.out``
      filename.

   -  ``mail-user``: Email to receive notification of job state changes.
      Default value ``""`` does not send any mail.

   -  ``mail-type``: Type of event to be notified by mail, can define
      several events separated by comma. Valid values
      ``NONE, BEGIN, END, FAIL, TIME_LIMIT, REQUEUE, ALL``. Default
      value ``""`` does not send any mail.

   -  ``reservation``: Allocate resources for the job from the named
      reservation. Default value ``""`` does not allocate from any named
      reservation.

   -  ``qos``: Request a quality of service for the job. Default value
      ``""`` lets de workload manager assign the default user ``qos``.

-  ``deployment``: Optional scripts to perform deployment operations
   (bootstrap and revert).

   -  ``bootstrap``: Relative path to blueprint to the script that will
      be executed in the HPC at the install workflow to bootstrap the
      job (like image download, data movements, etc.)

   -  ``revert``: Relative path to blueprint to the script that will be
      executed in the HPC at the uninstall workflow, reverting the
      bootstrap or other clean up operations (like removing the image).

   -  ``inputs``: List of inputs that will be passed to the scripts when
      executed in the HPC

-  ``skip_cleanup``: Set to true to not clean up orchestrator auxiliar
   files. Default ``False``.

..

   **Note**

   The variable $CURRENT_WORKDIR is available in all operations and
   scripts. It points to the working directory of the execution in the
   HPC from the *HOME* directory: ``/home/user/$CURRENT_WORKDIR/``.

   **Note**

   The variables $SCALE_INDEX, $SCALE_COUNT and $SCALE_MAX are available
   when scaling, holding for each job instance the index, the total
   number of instances, and the maximun in parallel respectively.

**Example**

This example demonstrates how to describe a new job executed in a
`Singularity <http://singularity.lbl.gov/>`__ instance.

.. code:: yaml

       singularity_job:
           type: croupier.nodes.SingularityJob
           properties:
               job_options:
                   pre:
                       - module load gcc/5.3.0 openmpi/1.10.2
                       - module load singularity/2.3.1
                       - touch pre.output
                   partition: 'thin-shared'
                   post:
                       - touch post.output
                   image: '$LUSTRE/openmpi_1.10.7_ring.img'
                   home: '$HOME:/home/$USER'
                   volumes:
                       - '/scratch'
                   command: 'ring > fourth_example_3.test'
                   nodes: 1
                   tasks: 1
                   tasks_per_node: 1
                   max_time: '00:01:00'
               deployment:
                   bootstrap: 'scripts/singularity_bootstrap_example.sh'
                   revert: 'scripts/singularity_revert_example.sh'
                   inputs:
                       - 'singularity_job'
   ...

**Mapped Operations:**

-  ``cloudify.interfaces.lifecycle.start`` Send and execute the
   bootstrap script.

-  ``cloudify.interfaces.lifecycle.stop`` Send and execute the revert
   script.

-  ``croupier.interfaces.lifecycle.queue`` Queues the job in the HPC.

-  ``croupier.interfaces.lifecycle.publish`` Publish outputs outside the HPC.

-  ``croupier.interfaces.lifecycle.cleanup`` Clean up operations after job is
   finished.

-  ``croupier.interfaces.lifecycle.cancel`` Cancels a queued job.

.. _relationships:

Relationships
=============

See the
`relationships <http://docs.getcloudify.org/4.1.0/blueprints/spec-relationships/>`__
section.

The following plugin relationship operations are defined in the HPC
plugin:

-  ``job_managed_by_wm`` Sets a `??? <#croupier.nodes.Job>`__ to be executed
   inside the target `??? <#croupier.nodes.WorkloadManager>`__.

-  ``job_depends_on`` Sets a `??? <#croupier.nodes.Job>`__ as a dependency of
   the target (another `??? <#croupier.nodes.Job>`__), so the target job
   needs to finish before the source can start.

-  ``wm_contained_in`` Sets a `??? <#croupier.nodes.WorkloadManager>`__ to be
   contained in the specific target (a computing node).

Tests
=====

To run the tests Cloudify CLI has to be installed locally. Example
blueprints can be found at *tests/blueprint* folder and have the
``simulate`` option active by default. Blueprint to be tested can be
changed at *workflows_tests.py* in the *tests* folder.

To run the tests against a real HPC / Monitor system, copy the file
*blueprint-inputs.yaml* to *local-blueprint-inputs.yaml* and edit with
your credentials. Then edit the blueprint commenting the simulate
option, and other parameters as you wish (e.g change the name ft2_node
for your own hpc name). To use the openstack integration, your private
key must be put in the folder *inputs/keys*.

   **Note**

   *dev-requirements.txt* needs to be installed
   (*windev-requirements.txt* for windows):

   .. code:: bash

      pip install -r dev-requirements.txt

   To run the tests, run tox on the root folder

   .. code:: bash

      tox -e flake8,py27
