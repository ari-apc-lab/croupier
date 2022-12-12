#! /bin/bash -e

ctx logger info "Starting request to http://datapublishmanager.itainnova.svc.cluster.local:8900/prediction"
response=$(curl http://datapublishmanager.itainnova.svc.cluster.local:8900/prediction)
ctx logger info "Request completed: ${response}"