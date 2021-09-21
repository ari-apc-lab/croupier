#!/bin/bash
module load miniconda3
conda activate met_env
python /mnt/netapp2/Store_uni/home/otras/gat/pma/a3_climate_model_workflow/MET_SCRIPTS/PRECIP_MET/download_precip_cds.py 12 192 ${GRAPEVINE}/AGROAPPS-CLIMATE-MODEL 2> error_precip_12.txt 1> output_precip_12.txt 
