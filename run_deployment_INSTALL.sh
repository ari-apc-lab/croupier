#!/bin/bash
export PYTHONPATH="$PYTHONPATH:`pwd`"
pipenv run python2 croupier_plugin/cli/cfy_INSTALL.py $1
