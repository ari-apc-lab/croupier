#!/bin/bash
module load miniconda3
conda activate test_env
# conda activate met_env
python $STORE/a3_climate_model_workflow/MET_SCRIPTS/TEMP_MET/download_cds_temp.py 12 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_temp_12.txt 1> output_temp_12.txt 
