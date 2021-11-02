#!/bin/bash

export shared=${GRAPEVINE}/ATOS-WORKSHOP
export script_file=${shared}/Codigo/test-$1.py
export PHENOLOGY_MODEL_LOCATION=$2
export OUTPUT_FILE_LOCATION=$3

cat << EOF > execute.sh
#!/bin/bash
module load miniconda3
export PHENOLOGY_MODEL_LOCATION=${PHENOLOGY_MODEL_LOCATION}
export OUTPUT_FILE_LOCATION=${OUTPUT_FILE_LOCATION}
conda activate ${shared}/grapevine
python ${script_file}
EOF