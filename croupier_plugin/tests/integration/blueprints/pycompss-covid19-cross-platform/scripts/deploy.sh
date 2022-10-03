#!/bin/bash
set -e

# keep track of the last executed command
trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
# echo an error message before exiting
trap 'echo "\"${last_command}\" command failed with exit code $?."' EXIT
# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

# read arguments
if [ "$#" -lt 6 ]; then
    echo "Illegal number of parameters.
    Usage: deploy -u|--user <hpc_user> -p|--password <hpc_password -k|--private_key <hcp_pkey> -h|--host <hpc_host> [-t|--token <github_token>].
    Provide either the password or the private key for target hpc" >&2
    exit 2
fi

POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--host)
      hpc_host="$2"
      shift # past argument
      shift # past value
      ;;
    -u|--user)
      hpc_user="$2"
      shift # past argument
      shift # past value
      ;;
    -p|--password)
      hpc_password="$2"
      shift # past argument
      shift # past value
      ;;
    -k|--private-key)
      hpc_pkey="$2"
      shift # past argument
      shift # past value
      ;;
    -t|--token)
      github_token="$2"
      shift # past argument
      shift # past value
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

if [ -z "$hpc_user" ]; then
  echo "Error: User not given"
  exit 1
fi

if [ -z "$hpc_pkey" ] && [ -z "$hpc_password" ]; then
  echo "Error: Either private key or password not given"
  exit 1
fi

if [ -z "$hpc_host" ]; then
  echo "Error: Host not given"
  exit 1
fi

# deletes the temp directory
function cleanup {
  rm -rf "$WORK_DIR"
  echo "Deleted temp working directory $WORK_DIR"
}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORK_DIR=$(mktemp -d -p "$DIR")
# check if tmp dir was created
if [[ ! "$WORK_DIR" || ! -d "$WORK_DIR" ]]; then
  echo "Could not create temp dir where to download Covid19 app"
  exit 1
fi

echo "Deploying Covid19 into temp working directory $WORK_DIR"
cd "$WORK_DIR" || exit

# Get Covid19 app from Github in temp folder
echo "Downloading Covid19 app into temp working directory $WORK_DIR"
if [ -z "$github_token" ]; then
  wget https://github.com/PerMedCoE/covid-19-workflow/archive/refs/heads/split-workflow.zip
else
  wget --header="Authorization: token $github_token" https://github.com/PerMedCoE/covid-19-workflow/archive/refs/heads/split-workflow.zip
fi

#Unzip repo
echo "Unzipping Covid19 app"
unzip split-workflow.zip covid-19-workflow-split-workflow/Resources/data/*
unzip split-workflow.zip covid-19-workflow-split-workflow/Workflow/PyCOMPSs/src_split/*

#Get Covid19 data files
wget https://www.ncbi.nlm.nih.gov/geo/download/?acc=GSE145926\&format=file -O GSE145926_RAW.tar
mkdir $WORK_DIR/GSE145926_covid19
tar xvf GSE145926_RAW.tar --directory $WORK_DIR/GSE145926_covid19
rm $WORK_DIR/GSE145926_covid19/*.csv.gz
mv $WORK_DIR/GSE145926_covid19 covid-19-workflow-split-workflow/Resources/data

#Rsync transfer Covid19 app and data to target HPC using user user's credentials and ssh
if [ -n "$hpc_pkey" ]; then
  echo "synchronizing Covid19 app to target HPC..."
  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $hpc_pkey" covid-19-workflow-split-workflow "$hpc_user"@"$hpc_host":permedcoe_apps/covid19
fi

if [ -n "$hpc_password" ]; then
  echo "synchronizing Covid19 app to target HPC..."
  rsync -ratlz --rsh="/usr/bin/sshpass -p $hpc_password ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l $hpc_user" covid-19-workflow-split-workflow  "$hpc_host":permedcoe_apps/covid19
fi


# Edit routes in covid-19-workflow-split-workflow/Resources/data/metadata_clean.ts

if [ -n "$hpc_pkey" ]; then
  echo "editing paths in covid-19-workflow-split-workflow/Resources/data/metadata_clean.ts..."
  pwd=`ssh -i "$hpc_pkey" "$hpc_user"@"$hpc_host" pwd`
  cmd="sed -i s+/apps/COMPSs/PerMedCoE/resources/covid-19-workflow/Resources/data/GSE145926_covid19+""$pwd""/permedcoe_apps/covid19/covid-19-workflow-split-workflow/Resources/data/GSE145926_covid19+ ""$pwd""/permedcoe_apps/covid19/covid-19-workflow-split-workflow/Resources/data/metadata_clean.tsv"
  ssh -i "$hpc_pkey" "$hpc_user"@"$hpc_host" "$cmd"
fi

if [ -n "$hpc_password" ]; then
  echo "editing paths in covid-19-workflow-split-workflow/Resources/data/metadata_clean.ts..."
  pwd=`sshpass -p "$hpc_password" ssh "$hpc_user"@"$hpc_host" pwd`
  cmd="sed -i s+/apps/COMPSs/PerMedCoE/resources/covid-19-workflow/Resources/data/GSE145926_covid19+""$pwd""/permedcoe_apps/covid19/covid-19-workflow-split-workflow/Resources/data/GSE145926_covid19+ ""$pwd""/permedcoe_apps/covid19/covid-19-workflow-split-workflow/Resources/data/metadata_clean.tsv"
  sshpass -p "$hpc_password" ssh "$hpc_user"@"$hpc_host" "$cmd"
fi

# Remove temp folder
cleanup






