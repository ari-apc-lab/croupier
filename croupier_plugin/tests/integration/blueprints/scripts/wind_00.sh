#!/bin/bash
module load miniconda3
conda activate test_env
# conda activate met_env

python $STORE/a3_climate_model_workflow/MET_SCRIPTS/WIND_MET/download_cds_wind.py 00 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_wind_00.txt 1> output_wind_00.txt 
