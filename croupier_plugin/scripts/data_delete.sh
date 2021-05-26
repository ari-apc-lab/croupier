#!/bin/bash

for file in "$@"
do
  rm -r "$file"
done
