#!/bin/bash

export shared=${STORE}/ATOS-WORKSHOP
export environment_file=${shared}/environment.yaml
export script_file=${shared}/Codigo/Train_hard_eat_healthy_sleep_well_and_repeat-Your_brain-$1.py
export PHENOLOGY_MODEL_LOCATION=$2
export OUTPUT_FILE_LOCATION=$3

cat << EOF > execute.sh
#!/bin/bash
export PHENOLOGY_MODEL_LOCATION=${PHENOLOGY_MODEL_LOCATION}
export OUTPUT_FILE_LOCATION=${OUTPUT_FILE_LOCATION}
conda env create --file ${environment_file}
source activate grapevine
python ${script_file}
EOF