# Submit a job to CESGA through Cloudify-Croupier Orchestrator - Part 2: Submit simple job using GUI 

### Create blueprint
This tutorial requires having completed [Part 1](https://github.com/ari-apc-lab/croupier/blob/grapevine/docs/Using_orchestrator_with_CESGA_part1.md) of this tutorial for downloading data inside CESGA and setting up the environment for code execution on CESGA. This tutorial does not involve programmatic upload/download of raw/processed data inside CESGA. This behaviour will be implemented later.

1. Go to the [Blueprint Template](https://github.com/ari-apc-lab/croupier/blob/permedcoe/croupier_plugin/tests/integration/blueprints/blueprint_single.yaml)
2. Press on `Raw` button, copy all the content and paste into you favourite code editor
3. Update the following fields of the blueprint:
    * `commands`: This is where you specify the exact (sequence of) command(s) you want to run inside CESGA back-end node (see examples below). When running more than one command, you should separate each command by adding a `;` at the end of each line, apart from the last line. It is also important that all code lines are aligned along the left side.  
    
    `touch test_$1.output`
    
    or
    
    ```#!/bin/bash
    module load miniconda3;
    conda activate tf_test2;
    srun python /home/otras/gat/pma/ITAINNOVA/Next_trials/Codigo/hard_copy.py
    ```
    * `max_time`: This is the amount of time you wish to reserve the back-end node on which the application will be running. It is in the format `hh:mm:ss`. You should always try to estimate the execution time of your job in the best possible way and not specify a too large value here. 
    
    * `nodes`, `tasks` and `tasks_per_node`: to be explained later; can be left as they are for now
    
4. Save blueprint file and update name (e.g. `blueprint_itainnova.yaml`)
5. Create new empty directory, then move blueprint file into directory
6. Zip directory and update name of zip file (e.g. `blueprint_itainnova.zip`)

### Specify additional blueprint inputs
1. Go to the [Blueprint Inputs Template](https://github.com/ari-apc-lab/croupier/blob/grapevine/croupier_plugin/tests/integration/inputs/blueprint-inputs.yaml)
2. Press on `Raw` button, copy all the content and paste into you favourite code editor
3. Update the following fields of the blueprint:


    * `host`: ft2.cesga.es
    * `user`: your username in CESGA
    * `password`: your password in CESGA
    * `private_key`: the private part of the RSA key (make sure the block of text is justified)
    
    ```#!/bin/bash
    private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    PRIVATEPART-OF-KEY
    ```
    
    * `partition_name`: the name of the partition to which you want to submit your job (for example, `gpu-shared`)
 
 4. Save blueprint file and update name (e.g. `blueprint_inputs.yaml`)
    
 
 ### Submit job using GUI 
 1. Brose to Cloudify Domain name GRAPEVINE project, and log in using credentials provided by Paolo Marangio
 2. Press on `Local Blueprints` tab, then press on grey button `Upload`
 3. Press on directory icon at the end of line below "Blueprint package"
 4. Navigate to the location on your computer where the blueprint zip file is saved, select it and press "Open"
 5. Press on green button `Upload`
 6. Press on `Deployments` tab, then press on green button `Create deployment`
 7. Enter Deployment name under `Deployment name` entry
 8. Press on entry below `Blueprint`, then select blueprint you have uploaded in steps 1-4
 9. Press on `Load Values` button
 10. Navigate to the location on your computer where the blueprint inputs file is saved, select it and press "Open"
 11. Repeat steps 8-9 (this is because Cloudify seems to not do anything the first time)
 12. Press on button "Deploy" at the bottom of the pop-up menu
 13. Press on `Deployments` tab, press on Deployment entry under `Deployments`
 14. Press on `Execute workflow` button, then select `Install` under "Default workflows" in the drop-down menu
 15. After logs show that previous step has been correctly executed, repeat step 13 but choose `Run jobs` under "Croupier" in the drop-down menu
 16. Continuously check logs confirming that job has been submitted to CESGA and executed successfully. 
 17. SSH into CESGA, enter directory associated with Cloudify-Croupier output under `$HOME` and inspect output
