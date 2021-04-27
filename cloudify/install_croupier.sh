#!/bin/bash
set -e

echo 'This script installs Cloudify and Croupier, overriding any preexisting installation'
echo 'Dependencies:'
echo '1- Docker running'
echo '2- Python 3.6 installed in path /usr/bin/python3.6, pip3.6 available'
read -p 'press any key to continue...'


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

#Cleanup
rm croupier-3.1.0-py36-none-linux_x86_64.wgn
rm ../../croupier.zip
rm -rf croupier-venv
