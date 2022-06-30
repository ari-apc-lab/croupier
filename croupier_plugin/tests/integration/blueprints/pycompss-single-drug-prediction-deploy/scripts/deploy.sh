#!/bin/bash
set -e

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

if [ -z "$hpc_host" ]; then
  echo "Error: Host not given"
  exit 1
fi

# deletes the temp directory
function cleanup {
  rm -rf "$WORK_DIR"
  echo "Deleted temp working directory $WORK_DIR"
}
# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORK_DIR=$(mktemp -d -p "$DIR")
# check if tmp dir was created
if [[ ! "$WORK_DIR" || ! -d "$WORK_DIR" ]]; then
  echo "Could not create temp dir where to download Single Drug Prediction app"
  exit 1
fi

echo "Deploying Single Drug Prediction into temp working directory $WORK_DIR"
cd "$WORK_DIR" || exit

# Get Single Drug Prediction app from Github in temp folder
echo "Downloading Single Drug Prediction app into temp working directory $WORK_DIR"
if [ -z "$github_token" ]; then
  wget https://github.com/PerMedCoE/single-drug-prediction-workflow/archive/refs/heads/main.zip
else
  wget --header="Authorization: token $github_token" https://github.com/PerMedCoE/single-drug-prediction-workflow/archive/refs/heads/main.zip
fi

#Unzip repo
echo "Unzipping Single Drug Prediction app"
unzip main.zip single-drug-prediction-workflow-main/Resources/data/*
unzip main.zip single-drug-prediction-workflow-main/Workflow/PyCOMPSs/src/*

#Rsync transfer Single Drug Prediction app and data to target HPC using user user's credentials and ssh
echo "Transferring Single Drug Prediction app to $hpc_host:permedcoe_apps/single-drug-prediction"
if [ -n "$hpc_pkey" ]; then
  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $hpc_pkey" single-drug-prediction-workflow-main "$hpc_user"@"$hpc_host":permedcoe_apps/single-drug-prediction
fi
if [ -n "$hpc_password" ]; then
  rsync -ratlz --rsh="/usr/bin/sshpass -p $hpc_password ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l $hpc_user" single-drug-prediction-workflow-main  "$hpc_host":permedcoe_apps/single-drug-prediction
fi

# Remove temp folder
cleanup






