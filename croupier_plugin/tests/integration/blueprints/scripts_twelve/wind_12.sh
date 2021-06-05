#!/bin/bash
module load miniconda3
conda activate met_env
python /mnt/netapp2/Store_uni/home/otras/gat/pma/a3_climate_model_workflow/MET_SCRIPTS/WIND_MET/download_cds_wind.py 12 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_wind_12.txt 1> output_wind_12.txt 
