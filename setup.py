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

setup.py
"""
import os

from setuptools import setup

# Replace the place holders with values for your project

setup(

    # Do not use underscores in the plugin name.
    name='croupier',

    version='3.3.0',
    author='Jesus Gorronogoitia',
    author_email='jesus.gorronogoitia@atos.net',
    description='Plugin to use HPC resources in Cloudify',

    # This must correspond to the actual packages in the plugin.
    packages=['croupier_plugin',
              'croupier_plugin.infrastructure_interfaces',
              'croupier_plugin.accounting_client',
              'croupier_plugin.accounting_client.model',
              'croupier_plugin.data_mover',
              'croupier_plugin.vault',
              'croupier_plugin.data_management'
              ],
    package_data={'croupier_plugin.infrastructure_interfaces': ['*.sh'],
                  'croupier_plugin': ['*.cfg'], 'croupier_plugin.data_management': ['*.sh']},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # Necessary dependency for developing plugins, do not remove!
        "cloudify-common==6.2.0",
        "paramiko==2.7.2",
        "pyyaml>=5.4",
        "wget",
        "future==0.18.3",
        "ckanapi"
    ],
    license='Apache APLv2.0'
)
