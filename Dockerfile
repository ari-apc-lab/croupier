FROM cloudifyplatform/community-cloudify-manager-aio
RUN  sed -i 's/admin_password: admin/admin_password: Euxdat12345!/g' /etc/cloudify/config.yaml
RUN /opt/mgmtworker/env/bin/pip install paramiko==2.7.1

