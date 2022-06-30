#!/bin/bash

# proxied_rsync.sh: copies data between two servers from proxy executing this command
# Script adapted from https://www.linode.com/community/questions/11486/top-tip-how-to-transfer-filesdirectories-between-servers

set -e

trap 'catch $? $LINENO' ERR
catch() {
  echo "proxied_rsync: error $1 occurred on line $2"
  cleanup
}

cleanup() {
  echo "proxied_rsync: cleanup"

  # unmount
  fusermount -u /tmp/sshfstmp

  # remove tmp directory
  rm -rf /tmp/sshfstmp 2>/dev/null
}

if [ $# -ne 8 ]; then
        echo 1>&2 "Usage: proxied_rsync [--source_password <source_password> | --source_private_key <path/to/key>] --source [user@]host:[dir]/[file] [--target_password <source_password> | --target_private_key <path/to/key>] --target [user@]host:[dir]"
        exit 127
fi

if [ ! -f /usr/bin/sshfs ]; then
        echo "sshfs: command not found."
        echo "The required 'fuse-sshfs or sshfs' package is not installed."
        exit 127
fi

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    --source_password)
      source_password="$2"
      echo 'source_password: ' "$source_password"
      shift # past argument
      shift # past value
      ;;
    --source_private_key)
      source_private_key="$2"
      echo 'source_private_key: ' "$source_private_key"
      shift # past argument
      shift # past value
      ;;
    --source)
      source="$2"
      echo 'source: ' "$source"
      shift # past argument
      shift # past value
      ;;
    --target_password)
      target_password="$2"
      echo 'target_password: ' "$target_password"
      shift # past argument
      shift # past value
      ;;
    --target_private_key)
      target_private_key="$2"
      echo 'target_private_key: ' "$target_private_key"
      shift # past argument
      shift # past value
      ;;
    --target)
      target="$2"
      echo 'target: ' "$target"
      shift # past argument
      shift # past value
      ;;
    *) # unknown option
      echo "Unknown argument $1, exiting ..."
      exit 127
      ;;
  esac
done

# Parsing source server, directory and file
re="([^:]+:)"
if [[ $source =~ $re ]]; then 
	source_endpoint=${BASH_REMATCH[1]}
	echo 'source_endpoint:' "$source_endpoint"
fi

re="[^:]+:(.*[/])"
if [[ $source =~ $re ]]; then 
	source_dir=${BASH_REMATCH[1]}
	echo 'source_dir:' "$source_dir"
fi

re="([^/^:]+$)"
if [[ $source =~ $re ]]; then 
	source_file=${BASH_REMATCH[1]}
	echo 'source_file:' "$source_file"
fi

if [ -z ${source_dir+x} ]; then 
	source_mount_point=$source_endpoint
else 
	source_mount_point="$source_endpoint$source_dir"
fi

echo "source_mount_point: " "$source_mount_point"

# Parsing target server, directory and file
re="([^:]+:)"
if [[ $target =~ $re ]]; then
	target_endpoint=${BASH_REMATCH[1]}
	target_endpoint=${target_endpoint::-1}
	echo 'target_endpoint:' "$target_endpoint"
fi

re="[^:]+:(.*[/])"
if [[ $target =~ $re ]]; then
	target_dir=${BASH_REMATCH[1]}
	target_dir=${target_dir::-1}
	echo 'target_dir:' "$target_dir"
fi

re="([^/^:]+$)"
if [[ $target =~ $re ]]; then
	target_file=${BASH_REMATCH[1]}
	echo 'target_file:' "$target_file"
fi

# remove stale tmp directory
rm -rf /tmp/sshfstmp

# create temporary directory
mkdir /tmp/sshfstmp
chmod go-wrx /tmp/sshfstmp

# mount sshfs
if [ -z ${source_private_key+x} ]; then
	#Using source_password for sshfs authentication
	echo "Invoking: sshfs -o password_stdin $source_mount_point /tmp/sshfstmp <<< '$source_password'"
	sshfs -o password_stdin "$source_mount_point" /tmp/sshfstmp <<< "$source_password"
elif [ -z ${source_password+x} ]; then
	#Using source_private_key for sshfs authentication
	echo "Invoking: sshfs -o StrictHostKeyChecking=no -oIdentityFile=$source_private_key $source_mount_point /tmp/sshfstmp"
	sshfs -o StrictHostKeyChecking=no -oIdentityFile="$source_private_key" "$source_mount_point" /tmp/sshfstmp
else
	echo "either source_password or source_private_key not set, exiting ..."
      	exit 127
fi

# rsync
if [ -z ${target_private_key+x} ]; then
	#Using target_password for rsync authentication
	#Create target folder if does not exist
	FLAGS="--safe-links -tarxlzhP"
	echo "Invoking: sshpass -p $target_password ssh -o StrictHostKeyChecking=no $target_endpoint mkdir -p $target_dir"
	sshpass -p "$target_password" ssh -o StrictHostKeyChecking=no "$target_endpoint" mkdir -p "$target_dir"
	if [ -z ${source_file+x} ]; then
		echo "Invoking: rsync --rsh="/usr/bin/sshpass -p "$target_password"" $FLAGS /tmp/sshfstmp/* $target"
		sshpass -p "$target_password" rsync "$FLAGS" /tmp/sshfstmp/* "$target"
	else
		echo "Invoking: rsync --rsh="/usr/bin/sshpass -p "$target_password"" $FLAGS /tmp/sshfstmp/$source_file $target"
		sshpass -p "$target_password" rsync "$FLAGS" /tmp/sshfstmp/"$source_file" "$target"
	fi
elif [ -z ${target_password+x} ]; then
	#Using target_private_key for rsync authentication
	#Create target folder if does not exist
	FLAGS="-e 'ssh -o StrictHostKeyChecking=no -i $target_private_key' --safe-links -tarxlzhP"
	echo "Invoking: ssh -o StrictHostKeyChecking=no -i $target_private_key $target_endpoint mkdir -p $target_dir"
	ssh -o StrictHostKeyChecking=no -i "$target_private_key" "$target_endpoint" mkdir -p "$target_dir"
	if [ -z ${source_file+x} ]; then
		echo Invoking: rsync "$FLAGS" /tmp/sshfstmp/* "$target"
		eval rsync "$FLAGS" /tmp/sshfstmp/* "$target"
	else
		echo Invoking: rsync "$FLAGS" /tmp/sshfstmp/"$source_file" "$target"
		eval rsync "$FLAGS" /tmp/sshfstmp/"$source_file" "$target"
	fi
else
	echo "either target_password or target_private_key not set, exiting ..."
      	exit 127
fi

cleanup
