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

Latest documentation can be found at [Read the Docs](https://croupier.readthedocs.io)

> **TIP:** Example blueprints can be found at the [Croupier resources repository](https://github.com/ari-apc-lab/croupier-resources).

## Install and Usage

As Cloudify plugin, Croupier needs to operate under a Cloudify Manager instance.
Check [Cloudify Docs](http://docs.getcloudify.org/4.5.5/intro/what-is-cloudify)
for general information about how to install and use Cloudify. To easily install
the manager, check the
[Croupier resources repository](https://github.com/ari-apc-lab/croupier-resources).

The plugin is installed as any other plugin. Using the [Croupier
CLI](https://github.com/ari-apc-lab/croupier-cli), it is easy to package the
plugin and install on a manager:

1. Clone this repository into your local folder, using `git clone https://github.com/ari-apc-lab/croupier.git`. Go to the created croupier folder.
2. Package Croupier as a Wagon archive: `wagon . -a '--no-cache-dir -c constraints.txt'`
3. Upload the plugin archive using the CLI: `cfy plugins upload *.wgn -y plugin.yaml -t default_tenant`
4. Alternatively, upload the plugin using the Cloudify GUI dashboard: Dashboard/Upload Plugin/. Select the Wagon file and plugin.yaml from the Croupier folder you cloned in step 1

## Setup a Python development environment
Croupier requires Python 2.7:

1. Install Python virtualenv: `pip install virtualenv`
2. Create a Python 2.7 virtual environment: `virtualenv -p /usr/bin/python2.7 croupier`
3. Activate environment: `source croupier/bin/activate`
4. Install Tox: `pip install tox`
In croupier folder, remove a pre-existing .tox folder
5. Run test cases: tox

## Test

To run the tests Cloudify CLI has to be installed locally. Example blueprints can be found at _tests/blueprint_ folder and have the `simulate` option active by default. Blueprint to be tested can be changed at _workflows_tests.py_ in the _tests_ folder.

To run the tests against a real HPC / Monitor system, copy the file _blueprint-inputs.yaml_ to _local-blueprint-inputs.yaml_ and edit with your credentials. Then edit the blueprint commenting the simulate option, and other parameters as you wish (e.g change the name ft2*node for your own hpc name). To use the openstack integration, your private key must be put in the folder \_inputs/keys*.

> **NOTE:** _tox_ needs to be installed: `pip install tox`

To run the tests, run tox on the root folder

```shell
tox -e flake8,unit,integration
```

## License

Croupier is licensed under [Apache License, Version 2.0 (the License)](./LICENSE)

## Legal disclaimer

The open source software and source code are provide to you on an “AS IS” basis and Atos Spain SA disclaim any and all warranties and representations with respect to such software and related source code, whether express, implied, statutory or otherwise, including without limitation, any implied warranties of title, non-infringement, merchantability, satisfactory quality, accuracy or fitness for a particular purpose.

Atos Spain SA shall not be liable to make any corrections to the open source software or source code, or to provide any support or assistance with respect to it without any previously specify agreement.

Atos Spain SA disclaims any and all liability arising out of or in connection with the use of this software and/or source code
