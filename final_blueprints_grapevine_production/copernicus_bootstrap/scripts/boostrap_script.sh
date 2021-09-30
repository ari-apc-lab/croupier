#!/bin/bash
date
module load miniconda3
conda activate met_env
python /mnt/netapp2/Store_uni/home/otras/gat/pma/met_test_a3_climate_model/a3_climate_model_workflow/MET_SCRIPTS/TEMP_MET/download_cds_temp.py 2021-04-06 00 192 $LUSTRE 2> error1.txt 1> output1.txt
date 
