# Croupier

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[Cloudify](http://cloudify.co/) plugin for HPC and batch jobs orchestration. Combined with other plugins, it can orchestrate a hybrid cloud+hpc environment, with one or more cloud and hpc providerds at the same time.

> **NOTE:** Originally developed under the H2020 project [Croupier H2020 European Project](http://www.croupier.eu/): <https://github.com/ari-apc-lab/croupier>

## Contents

- [Documentation](#documentation)
- [Install and Usage](#install-and-usage)
- [Test](#test)
- [License](#license)
- [Legal disclaimer](#legal-disclaimer)

## Documentation

TODO reference to readthedocs

> **TIP:** Example blueprints can be found at the [Croupier resources repository](https://github.com/ari-apc-lab/croupier-resources).

## Install and Usage

The plugin is installed as any other plugin. Check [Cloudify Docs](http://docs.getcloudify.org/4.5.5/intro/what-is-cloudify) for general information about how to install and use Cloudify, and [this section](http://docs.getcloudify.org/4.1.0/plugins/using-plugins) for concrete information about using plugins.

Additionally, Croupier provides [Vagrant](https://www.vagrantup.com/) and [Docker](https://www.docker.com/) images at [croupier-cli](https://github.com/ari-apc-lab/croupier-cli) to remotely install and operate with the orchestrator. An already built docker image is also available at [Docker Hub](https://hub.docker.com/u/croupier/dashboard/).

## Test

To run the tests Cloudify CLI has to be installed locally. Example blueprints can be found at *tests/blueprint* folder and have the `simulate` option active by default. Blueprint to be tested can be changed at *workflows\_tests.py* in the *tests* folder.

To run the tests against a real HPC / Monitor system, copy the file *blueprint-inputs.yaml* to *local-blueprint-inputs.yaml* and edit with your credentials. Then edit the blueprint commenting the simulate option, and other parameters as you wish (e.g change the name ft2\_node for your own hpc name). To use the openstack integration, your private key must be put in the folder *inputs/keys*.

> **NOTE:** *tox* needs to be installed: `pip install tox`

To run the tests, run tox on the root folder

```shell
tox -e flake8,py27
```

## License

Croupier is licensed under [Apache License, Version 2.0 (the License)](./LICENSE)

## Legal disclaimer

The open source software and source code are provide to you on an “AS IS” basis and Atos Spain SA disclaim any and all warranties and representations with respect to such software and related source code, whether express, implied, statutory or otherwise, including without limitation, any implied warranties of title, non-infringement, merchantability, satisfactory quality, accuracy or fitness for a particular purpose.

Atos Spain SA shall not be liable to make any corrections to the open source software or source code, or to provide any support or assistance with respect to it without any previously specify agreement.

Atos Spain SA disclaims any and all liability arising out of or in connection with the use of this software and/or source code