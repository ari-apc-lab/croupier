#!/bin/bash
module load miniconda3
conda activate met_env
python /mnt/netapp2/Store_uni/home/otras/gat/pma/a3_climate_model_workflow/MET_SCRIPTS/TEMP_MET/download_cds_temp.py 12 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_temp_12.txt 1> output_temp_12.txt 
