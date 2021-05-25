#!/usr/bin/env bash

for url in "$@"
do
  wget "$url"
  filename=$(basename "$url")
  unzip "$filename"
  rm "$filename"
done