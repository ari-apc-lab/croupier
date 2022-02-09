FROM cloudifyplatform/community-cloudify-manager-aio:6.2.0
RUN yum install epel-release -y
RUN yum install certbot python2-certbot-nginx -y
RUN sed -i "s/set_cmd += \['-c', cert_path, '--ssl', 'on'\]/set_cmd += \['--ssl', 'on'\]/g" /opt/cloudify/cfy_manager/lib/python3.6/site-packages/cfy_manager/components/cli/cli.py
RUN sed -i "s/'-untrusted', cert_filename,/'-untrusted', cert_filename, '-partial_chain',/g" /opt/cloudify/cfy_manager/lib/python3.6/site-packages/cfy_manager/components/validations.py