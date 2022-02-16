#!/bin/bash
set -e

while getopts 'hb:' OPTION; do
  case "$OPTION" in
    h)
      echo "Usage: $0 [-b blueprint_folder] " >&2
      exit 1
      ;;
    b)
      blueprints_folder="$OPTARG"
      ;;
    esac
done

echo 'This script installs Cloudify and Croupier, overriding any preexisting installation'
echo 'Eventually, it can install the zipped blueprints located at given folder with option -b <path>'
echo 'The name of the blueprint yaml contained in the zip file must be blueprint.yaml'
echo 'Dependencies:'
echo '1- Docker running'
echo '2- Python 3.6 installed in path /usr/bin/python3.6, pip3.6 available'
echo '3- wget installed'
read -p 'press any key to continue...'

#Install Cloudify CLI
if ! rpm -q cloudify-cli; then
  wget https://repository.cloudifysource.org/cloudify/5.2.0/ga-release/cloudify-cli-5.2.0-ga.el7.x86_64.rpm
  sudo rpm -Uhv --nodeps cloudify-cli-5.2.0-ga.el7.x86_64.rpm
fi

#Run Cloudify
docker stop cfy_manager_local || true && docker rm cfy_manager_local || true
sudo docker run --name cfy_manager_local -d --restart unless-stopped -v /sys/fs/cgroup:/sys/fs/cgroup:ro --tmpfs /run --tmpfs /run/lock --security-opt seccomp:unconfined --cap-add SYS_ADMIN -p 80:80 -p 8000:8000 cloudifyplatform/community-cloudify-manager-aio:5.2.0

#Prepare Python3.6 virtual environment
pip3.6 install virtualenv
virtualenv -p /usr/bin/python3.6 croupier-venv
source croupier-venv/bin/activate
pip install -r ../dev-requirements.txt
 
#Create Croupier Wagon
pip install wagon
zip -r ../../croupier.zip ../../croupier -x \*croupier/.*
wagon create -f ../../croupier.zip -a '--no-cache-dir -c ../../croupier/constraints.txt'

#Install Croupier in Cloudify
until cfy profiles use localhost -t default_tenant -u admin -p admin; do
  echo Trying to connect to Cloudify ...
  sleep 5
done

cfy plugins upload croupier-3.1.0-py36-none-linux_x86_64.wgn -y ../../croupier/plugin.yaml -t default_tenant

#Install blueprints from given folder
if [ -n "$blueprints_folder" ]; then
  echo "Installing blueprints from folder $blueprints_folder"
  for blueprint in "$blueprints_folder"/*; do
    if [[ $blueprint == *.zip ]]; then
      echo "Installing blueprint " $blueprint
      cfy blueprints upload -a $blueprint
    fi
  done
fi

#Cleanup
rm croupier-3.1.0-py36-none-linux_x86_64.wgn
rm ../../croupier.zip
rm -rf croupier-venv
