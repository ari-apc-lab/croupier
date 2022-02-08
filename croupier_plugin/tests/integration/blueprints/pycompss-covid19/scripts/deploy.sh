#!/bin/bash

# read arguments

if [ "$#" -lt 6 ]; then
    echo "Illegal number of parameters. Usage deploy: -u|--user <user> -p|--password <password -k|--private_key <key> - h|--host <host>. Provide either the password or the key" >&2
    exit 2
fi

POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--host)
      host="$2"
      shift # past argument
      shift # past value
      ;;
    -u|--user)
      user="$2"
      shift # past argument
      shift # past value
      ;;
    -p|--password)
      password="$2"
      shift # past argument
      shift # past value
      ;;
    -k|--private-key)
      pkey="$2"
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

if [ -z "$user" ]; then
  echo "Error: User not given"
  exit 1
fi

if [ -z "$host" ]; then
  echo "Error: Host not given"
  exit 1
fi

# deletes the temp directory
function cleanup {
  rm -rf "$WORK_DIR"
  echo "Deleted temp working directory $WORK_DIR"
}
# register the cleanup function to be called on the EXIT signal
# trap cleanup EXIT


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
wget https://github.com/PerMedCoE/PilotWorkflow/archive/refs/heads/main.zip

#Unzip repo
unzip main.zip PilotWorkflow-main/resources/data/*
unzip main.zip PilotWorkflow-main/covid19_pilot_workflow/PyCOMPSs/*

#Rsync transfer Covid19 app and data to target HPC using user user's credentials and ssh
if [ -n "$pkey" ]; then
  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $pkey" PilotWorkflow-main $user@$host:permedcoe_apps/covid19
fi
if [ -n "$password" ]; then
  rsync -ratlz --rsh="/usr/bin/sshpass -p $password ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l $user" PilotWorkflow-main  $host:permedcoe_apps/covid19
fi

# Remove temp folder
cleanup






