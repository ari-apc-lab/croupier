#!/bin/bash

# read arguments

if [ "$#" -lt 6 ]; then
    echo "Illegal number of parameters. Usage revert -u|--user <user> -p|--password <password -k|--private_key <key> - h|--host <host>. Provide either the password or the key" >&2
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
      echo "Unknown option $1. Ignoring" #Ignoring other inputs, since same inputs are given for deploy and revert scripts
      shift # past argument
      shift # past value
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

if [ -n "$pkey" ]; then
  ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i $pkey $user@$host 'rm -rf permedcoe_apps/covid19/'
fi
if [ -n "$password" ]; then
  sshpass -p "$password" ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no $user@$host 'rm -rf permedcoe_apps/covid19/'
fi
