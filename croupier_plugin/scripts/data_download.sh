#!/usr/bin/env bash

for url in "$@"
do
  wget $url
done