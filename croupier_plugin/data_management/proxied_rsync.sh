#!/bin/bash

# proxied_rsync.sh: copies data between two servers from proxy executing this command
# Script adapted from https://www.linode.com/community/questions/11486/top-tip-how-to-transfer-filesdirectories-between-servers

set -e

if [ $# -ne 2 ]; then
        echo 1>&2 Usage: proxied_rsync [user@]host:[dir]/[file] [user@]host:[dir]
        exit 127
fi

if [ ! -f /usr/bin/sshfs ]; then
        echo "sshfs: command not found."
        echo "The required 'fuse-sshfs or sshfs' package is not installed."
        exit 127
fi

# Parsing source server, directory and file
re="([^:]+:)"
if [[ $1 =~ $re ]]; then 
	source_endpoint=${BASH_REMATCH[1]}
	#echo 'source_endpoint:' $source_endpoint
fi

re="[^:]+:(.*[/])"
if [[ $1 =~ $re ]]; then 
	source_dir=${BASH_REMATCH[1]}
	#echo 'source_dir:' $source_dir
fi

re="([^/^:]+$)"
if [[ $1 =~ $re ]]; then 
	source_file=${BASH_REMATCH[1]}
	#echo 'source_file:' $source_file
fi

if [ -z ${source_dir+x} ]; then 
	source_mount_point=$source_endpoint
else 
	source_mount_point="$source_endpoint$source_dir"
fi

echo "source_mount_point: " $source_mount_point


# remove stale tmp directory
rm -rf /tmp/sshfstmp 2>/dev/null

# create temporary directory
mkdir /tmp/sshfstmp
chmod go-wrx /tmp/sshfstmp

# mount sshfs
sshfs "$source_mount_point" /tmp/sshfstmp

# rsync
if [ -z ${source_file+x} ]; then 
	rsync --safe-links -tarxlzhP /tmp/sshfstmp/ "$2"
else
	rsync --safe-links -tarxlzhP /tmp/sshfstmp/"$source_file" "$2"
fi

# unmount
fusermount -u /tmp/sshfstmp

# remove tmp directory
rm -rf /tmp/sshfstmp 2>/dev/null
