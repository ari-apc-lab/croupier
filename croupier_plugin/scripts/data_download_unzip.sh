#!/usr/bin/env bash

for url in "$@"
do
  wget "$url"
  filename=$(basename "$url")
  tar -xzf "$filename"
done