#!/bin/bash

for url in "$@"
do
  wget "$url"
done
