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
  |manager.rst


============
Installation
============

Croupier, as a Cloudify plugin, must to be run inside the Cloudify Server, a.k.a Cloudify Manager. This section describes how to install Cloudify Manager, with the Croupier plugin.

Cloudify Manager
================

Docker
------

Cloudify provides a docker image of the manager. It cannot be configured so, among other things, it is not secure (user admin/admin).

.. code:: bash

  sudo docker run --name cfy_manager -d --restart unless-stopped \
    -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
    --tmpfs /run \
    --tmpfs /run/lock \
    --security-opt seccomp:unconfined \
    --cap-add SYS_ADMIN \
    --network host \
    cloudifyplatform/community:19.01.24


OpenStack plugin (Optional)

.. code:: bash

  cfy plugins upload \
    -y http://www.getcloudify.org/spec/openstack-plugin/2.14.7/plugin.yaml \
    http://repository.cloudifysource.org/cloudify/wagons/cloudify-openstack-plugin/2.14.7/cloudify_openstack_plugin-2.14.7-py27-none-linux_x86_64-centos-Core.wgn


Requirements
------------

Cloudify Manager is supported for installation on a 64-bit host with RHEL/CentOS 7.4.

+---------+---------+-------------+
|         | Minimum | Recommended |
+=========+=========+=============+
| vCPUs   | 2       | 8           |
+---------+---------+-------------+
| RAM     | 4GB     | 16GB        |
+---------+---------+-------------+
| Storage | 5GB     | 64GB        |
+---------+---------+-------------+

The minimum requirements are enough for small deployments that only manage a few compute instances. Managers that manage more deployments or large deployments need at least the recommended resources.

Check `Cloudify docs <https://docs.cloudify.co/4.5.5/install_maintain/installation/prerequisites/>`__ for full prerequisites details.

Croupier Plugin
===============

TODO