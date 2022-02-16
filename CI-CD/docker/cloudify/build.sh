#!/bin/bash

CFY_VERSION=6.2.0
export IMAGE_NAME=cloudify_certbot
export TAG_NAME=${CFY_VERSION}

# Build the docker image
docker build --rm=true -t $IMAGE_NAME:$TAG_NAME .
docker push atosariapclab/${IMAGE_NAME}:$TAG_NAME
docker push atosariapclab/${IMAGE_NAME}:latest