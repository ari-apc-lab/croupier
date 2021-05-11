#!/bin/bash

export IMAGE_NAME=cloudify-croupier
export TAG_NAME=latest

# Build the docker image
docker build --rm=true -t $IMAGE_NAME:$TAG_NAME .

