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
  echo "Could not create temp dir where to download Drug Synergies app"
  exit 1
fi

echo "Deploying Drug Synergies into temp working directory $WORK_DIR"
cd "$WORK_DIR" || exit

# Get Drug Synergies app from Github in temp folder
echo "Downloading Drug Synergies app into temp working directory $WORK_DIR"
if [ -z "$github_token" ]; then
  wget https://github.com/PerMedCoE/drug-synergies-workflow/archive/refs/heads/main.zip
else
  wget --header="Authorization: token $github_token" https://github.com/PerMedCoE/drug-synergies-workflow/archive/refs/heads/main.zip
fi

#Unzip repo
echo "Unzipping Drug Synergies app"
unzip main.zip drug-synergies-workflow-main/Resources/data/*
unzip main.zip drug-synergies-workflow-main/Workflow/PyCOMPSs/src/*
tar xvzf drug-synergies-workflow-main/Resources/data/data_celllines.tar.gz --directory drug-synergies-workflow-main/Resources/data

#Rsync transfer Drug Synergies app and data to target HPC using user user's credentials and ssh
echo "Transferring Drug Synergies app to $hpc_host:permedcoe_apps/drug-synergies"
if [ -n "$hpc_pkey" ]; then
  ssh -o StrictHostKeyChecking=no -i "$hpc_pkey" "$hpc_user"@"$hpc_host" mkdir -p permedcoe_apps/drug-synergies
  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $hpc_pkey" drug-synergies-workflow-main "$hpc_user"@"$hpc_host":permedcoe_apps/drug-synergies
fi
if [ -n "$hpc_password" ]; then
  sshpass -p $hpc_password ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no "$hpc_user"@"$hpc_host" mkdir -p permedcoe_apps/drug-synergies
  rsync -ratlz --rsh="/usr/bin/sshpass -p $hpc_password ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l $hpc_user" drug-synergies-workflow-main  "$hpc_host":permedcoe_apps/drug-synergies
fi

# Remove temp folder
cleanup






