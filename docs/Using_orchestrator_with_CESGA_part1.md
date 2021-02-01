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

## Set up environment for execution on **CPU** 
### Create conda virtual environment on CESGA with tensorflow **CPU** 

1. SSH into ft2.cesga.es
2. `unzip Next_trials_ITAINNOVA.zip`
3. Download Miniconda: `wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh`
4. Install Miniconda: `bash Miniconda3-latest-Linux-x86_64.sh`\
4A. When prompted during installation, specify `$STORE` as location for installing Miniconda


*Miniconda3 will now be installed into this location:*
*/home/otras/gat/<3-letter-username>/miniconda3*

  *- Press ENTER to confirm the location*\
  *- Press CTRL-C to abort the installation*\
  *- Or specify a different location below*

*[/home/otras/gat/<3-letter-username>/miniconda3] >>>* **$STORE**

5. `. ~/.bashrc`
6. `cd Next_trials_ITAINNOVA/Next trials/`
7. Create conda virtual environment named "grapevine" from requirements file: `conda env create --file environment.yml`

### Run test script on CESGA to verify correct installation using interactive **CPU** node 
1. `compute -c 2 --mem 5 --x11` (2 is the number of cores; If you increase this, you will ask for more cores, but you may not obtain the cores immediately)
2. Provide CESGA password in order to connect to interactive node 
3. `/mnt/netapp2/Store_uni/home/otras/gat/<3-letter-username>/bin/miniconda3/bin/conda activate grapevine`
4. `export PATH=/mnt/netapp2/Store_uni/home/otras/gat/<3-letter-username>/bin/miniconda3/envs/grapevine/bin:$PATH`
5. `cd Next_trials_ITAINNOVA/Next trials/Codigo/`
6. `python easy.py`
7. Exit from the interactive node: `exit`

## Set up environment for execution on **GPU** 

### Create conda virtual environment on CESGA with tensorflow **GPU**
1. Perform all steps as for CPU version above for creation of conda virtual environment
2. `conda activate grapevine`
3. `module load cuda/10.0.130`
4. `pip install --upgrade tensorflow-gpu=1.15.0`
5. `conda deactivate`

### Run test script on CESGA to verify correct installation using interactive **GPU** node 
1. `compute --gpu` 
2. `/mnt/netapp2/Store_uni/home/otras/gat/<3-letter-username>/bin/miniconda3/bin/conda activate grapevine`
3. `export PATH=/mnt/netapp2/Store_uni/home/otras/gat/<3-letter-username>/bin/miniconda3/envs/grapevine/bin:$PATH`
4. `module load cuda/10.0.130`
5. `cd Next_trials_ITAINNOVA/Next trials/Codigo/`
6. `python medium.py`
7. Exit from the interactive node: `exit`

### Run test script on CESGA to verify correct installation using back-end node
TODO
