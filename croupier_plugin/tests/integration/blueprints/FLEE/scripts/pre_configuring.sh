#!/bin/bash -l

LOGFILE="pre_configuring_log.txt"


cat << EOF_LOGFILE > $LOGFILE
log pre_configuring.sh ...

flee_github_repo = $1
branch =  $2
config_name = $3
simulation_period = $4
parallel_mode = $5
jobmanager_type = $6
nnodes = $7
ncorespernode = $8
inputconfigtags = $9
mscale = ${10}
mscale_num_instances = ${11}
mscale_cores_per_instance = ${12}
mscale_input_data_dir = ${13}
mscale_log_exchange_data = ${14}
mscale_coupling_type = ${15}
mscale_weather_coupling = ${16}
EOF_LOGFILE


CFGFILE="flee.cfg"
id=`cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 6 | head -n 1`
cat << EOF_CFGFILE > $CFGFILE
FLEE_GITHUB_REPO=$1
REPO_BRANCH=$2
CONFIG_NAME=$3
SIMULATION_PERIOD=$4
PARALLEL_MODE=$5
JOBMANAGER=$6
NUMBER_OF_NODES=$7
NUMBER_OF_CORES_PER_NODE=$8
INPUT_CONFIG_TAGS=$9
MSCALE=${10}
MSCALE_NUM_INSTANCES=${11}
MSCALE_CORES_PER_INSTANCE=${12}
MSCALE_INPUT_DATA_DIR=${13}
MSCALE_LOG_EXCHANGE_DATA=${14}
MSCALE_COUPLING_TYPE=${15}
MSCALE_WEATHER_COUPLING=${16}
ID=$id
CURDIR=$PWD
EOF_CFGFILE

source $CFGFILE

cat << EOF_RUNFILE > $run_job.sh
#!/bin/bash -l

#----------------------------------------
#        load ENV variables
#----------------------------------------
CFGFILE="flee.cfg"
source $CFGFILE

#----------------------------------------
#     Cloning FLEE application
#----------------------------------------
git clone -b $REPO_BRANCH $FLEE_GITHUB_REPO

#----------------------------------------
#     Add FLEE to PYTHONPATH
#----------------------------------------
cat << EOF_CFGFILE >> $CFGFILE
export PYTHONPATH=$PWD/flee:\$PYTHONPATH
EOF_CFGFILE

source $CFGFILE

#----------------------------------------------
#     Install python required packages by FLEE
#----------------------------------------------
pip3 install --user -r $PWD/flee/requirements.txt


#----------------------------------------
#     RUN job
#----------------------------------------
LOG_RUN_JOB='run_job.log'
echo "PYTHONPATH = " $PYTHONPATH > $LOG_RUN_JOB

cd $CONFIG_NAME

# covert to lowercase
MSCALE=$(echo "$MSCALE" | tr "[:upper:]" "[:lower:]")
PARALLEL_MODE=$(echo "$PARALLEL_MODE" | tr "[:upper:]" "[:lower:]")
MSCALE_COUPLING_TYPE=$(echo "$MSCALE_COUPLING_TYPE" | tr "[:upper:]" "[:lower:]")




if [ "$MSCALE" == "false" ]
then

    if [ "$PARALLEL_MODE" == "true" ]
    then
        echo "PARALLEL_MODE is enabled . . ." | tee -a "$LOG_RUN_JOB"
        mpirun -n $NUMBER_OF_CORES_PER_NODE python3 run_par.py input_csv source_data $SIMULATION_PERIOD simsetting.csv > out.csv
    else
        echo "PARALLEL_MODE is disabled . . ." | tee -a "$LOG_RUN_JOB"
        python3 run.py input_csv source_data $SIMULATION_PERIOD simsetting.csv > out.csv
    fi

else
    pip3 install --user -U muscle3
    if [ "$MSCALE_COUPLING_TYPE" == "file" ]
    then
        echo "Run file-mode multi-scale simulation . . ." | tee -a "$LOG_RUN_JOB"
        bash run_file_coupling.sh --NUM_INSTANCES $MSCALE_NUM_INSTANCES --cores $MSCALE_CORES_PER_INSTANCE --INPUT_DATA_DIR $MSCALE_INPUT_DATA_DIR --LOG_EXCHANGE_DATA $MSCALE_LOG_EXCHANGE_DATA --WEATHER_COUPLING $MSCALE_WEATHER_COUPLING
    fi

fi

cd ..


#----------------------------------------
#     Zip output results
#----------------------------------------

result_file_name=$CONFIG_NAME'-results-'$(whoami)'-'$ID'-'$(date +'[%H:%M:%S][%m-%d-%Y]')

cat << EOF_CFGFILE >> $CFGFILE
RESULT_FILE_NAME=$result_file_name
EOF_CFGFILE

source flee.cfg

env > env.log
/usr/bin/env > env2.log

zip -r $result_file_name *.err *.out *.script *.yaml $CONFIG_NAME
EOF_RUNFILE
