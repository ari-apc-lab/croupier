'''
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

setup.py
'''


from setuptools import setup

# Replace the place holders with values for your project

setup(

    # Do not use underscores in the plugin name.
    name='croupier',

    version='3.0.0',
    author='Javier Carnero',
    author_email='javier.carnero@atos.net',
    description='Plugin to use HPC resources in Cloudify',

    # This must correspond to the actual packages in the plugin.
    packages=['croupier_plugin',
              'croupier_plugin.infrastructure_interfaces',
              'croupier_plugin.external_repositories',
              'croupier_plugin.accounting_client',
              'croupier_plugin.accounting_client.model',
              'croupier_plugin.data_mover',
              'croupier_plugin.monitoring',
              ],
    package_data={'croupier_plugin.infrastructure_interfaces': ['*.sh'],
                  'croupier_plugin': ['*.cfg']},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # Necessary dependency for developing plugins, do not remove!
        "cloudify-common>=5.0.5",
        "paramiko==2.7.2",
        "pyyaml",
        "wget"
    ],
    license='LICENSE'
)
