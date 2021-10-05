#!/bin/bash
module load miniconda3
conda activate test_env
#conda activate met_env
python $STORE/a3_climate_model_workflow/MET_SCRIPTS/PRECIP_MET/download_precip_cds.py 00 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_precip_00.txt 1> output_precip_00.txt 
