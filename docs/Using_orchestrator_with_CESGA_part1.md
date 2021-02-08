# Submit a job to CESGA through Cloudify-Croupier Orchestrator - Part 1: Installation/Setting up before running orchestrator
### Transfer files/code into CESGA using SFTP (slow)
1. Download and install [MobaXterm](https://mobaxterm.mobatek.net/) client on personal machine
2. Click on "Session", then "SFTP", then specify ft2.cesga.es for Remote host and your CESGA username for Username, and press "OK"
3. Drag "Next_trials_ITAINNOVA.zip" from location in personal machine to location inside CESGA home directory. Transfer will start automatically.

### Add RSA public key in list of autherized keys in CESGA 
1. Create RSA key pair on private machine using OpenSSH (e.g. `ssh-keygen`)
2. SSH into ft2.cesga.es
3. Create new file named "authorized_keys" inside ".ssh" and paste public part of RSA key
4. `chmod 600 .ssh/authorized_keys`

### Create conda virtual environment on CESGA with tensorflow **GPU**
1. SSH into ft2.cesga.es
2. `module load miniconda3`
3. `conda config --set auto_activate_base false`
4. `conda create -n tf_test tensorflow=2.2.0=gpu_py37h1a511ff_0`
5. `pip install optuna keras scikit-learn pandas`

### Run test script on CESGA to verify correct installation using interactive **GPU** node 
1. Start interactive session to GPU node: `compute --gpu`
2. `conda activate tf_test`
3. `cd Next_trials_ITAINNOVA/Next trials/Codigo/`
4. `python medium.py`or `python hard.py`
5. Exit from the interactive node: `exit`

### Run test script on CESGA to verify correct installation using back-end node (requires code refactoring for reading/writing to path in HPC)
1. Create `.sh` file and add the following as content:
```#!/bin/bash
#SBATCH -t 0:20:00
#SBATCH -p gpu-shared
#SBATCH --gres gpu:1
#SBATCH --qos=urgent
#SBATCH --job-name my_python_code

module load miniconda3
conda activate tf_test

srun python /home/otras/gat/<3-letter-usernane-in-CESGA>/Next_trials/Codigo/hard.py
```
2. Submit batch job: `sbatch file_backend_execution.sh`
3. Check job execution status: `squeue`
4. Inspect output: `cat slurm-<job id>.out`
