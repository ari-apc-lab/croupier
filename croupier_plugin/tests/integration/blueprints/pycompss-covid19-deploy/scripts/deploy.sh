#!/bin/bash
set -e

# read arguments

if [ "$#" -lt 6 ]; then
    echo "Illegal number of parameters.
    Usage: deploy -u|--user <user> -p|--password <password -k|--private_key <key> -h|--host <hpc_host> [-t|--token <github_token>].
    Provide either the password or the private key for target hpc" >&2
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
    -t|--token)
      token="$2"
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
if [ -z "$token" ]; then
  wget https://github.com/PerMedCoE/covid-19-workflow/archive/refs/heads/main.zip
else
  wget --header="Authorization: token $token" https://github.com/PerMedCoE/covid-19-workflow/archive/refs/heads/main.zip
fi

#Unzip repo
unzip main.zip covid-19-workflow-main/Resources/data/*
unzip main.zip covid-19-workflow-main/Workflow/PyCOMPSs/src/*

#Rsync transfer Covid19 app and data to target HPC using user user's credentials and ssh
if [ -n "$pkey" ]; then
  rsync -ratlz -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $pkey" covid-19-workflow-main $user@$host:permedcoe_apps/covid19
fi
if [ -n "$password" ]; then
  rsync -ratlz --rsh="/usr/bin/sshpass -p $password ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -l $user" covid-19-workflow-main  $host:permedcoe_apps/covid19
fi

# Remove temp folder
cleanup






