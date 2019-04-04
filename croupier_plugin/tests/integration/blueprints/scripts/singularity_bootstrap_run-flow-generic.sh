#!/bin/bash -l

########
# Copyright (c) 2019 Atos Spain SA. All rights reserved.
#
# This file is part of Croupier.
#
# Croupier is free software: you can redistribute it and/or modify it
# under the terms of the Apache License, Version 2.0 (the License) License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT, IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
# OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# See README file for full disclaimer information and LICENSE file for full
# license information in the project root.
#
# @author: Javier Carnero
#          Atos Research & Innovation, Atos Spain S.A.
#          e-mail: javier.carnero@atos.net
#
# singularity_bootstrap_run-flow-generic.sh


module load singularity/2.4.2

REMOTE_URL=$1
IMAGE_URI=$2
IMAGE_NAME=$3

# cd $CURRENT_WORKDIR ## not needed, already started there
singularity pull --name $IMAGE_NAME $IMAGE_URI
wget $REMOTE_URL
ARCHIVE=$(basename $REMOTE_URL)
tar zxvf $ARCHIVE
DIRNAME=$(basename $ARCHIVE .tgz)
DECK=$(ls $DIRNAME/*.DATA)
cat << EOF > run_generated.param
ecl-deck-file-name=$(readlink -m $CURRENT_WORKDIR)/$DECK
EOF

singularity pull --name remotelogger-cli.simg shub://sregistry.srv.cesga.es/croupier/remotelogger-cli:latest
mkdir -p simoutput
JOB_LOG_FILTER_FILE='logfilter.yaml'
cat << EOF > $JOB_LOG_FILTER_FILE
[
    {
        "filename": "$OUTPUTDIR/.$PREFIXDECK.DEBUG",
        "filters": [
            {pattern: "^================    End of simulation     ===============", severity: "OK"},
            {pattern: "^Time step",  severity: "INFO", maxprogress: 247},
            {pattern: "^Report step",  severity: "WARNING", progress: "+1"},
            {pattern: "^[\\\\s]*[:|=]", verbosity: 2},
            {pattern: "^Keyword", verbosity: 1},
            {pattern: "[\\\\s\\\\S]*", skip: True},
        ]
    }
]
EOF




