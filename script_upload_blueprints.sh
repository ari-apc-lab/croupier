#!/bin/bash
set -e

while getopts 'hb:' OPTION; do
  case "$OPTION" in
    h)
      echo "Usage: $0 [-b blueprint_folder] " >&2
      exit 1
      ;;
    b)
      blueprints_folder="$OPTARG"
      ;;
    esac
done

if [ -n "$blueprints_folder" ]; then
  echo "Installing blueprints from folder $blueprints_folder"
  for blueprint in "$blueprints_folder"/*; do
    if [[ $blueprint == *.zip ]]; then
      echo "Installing blueprint " $blueprint
      cfy blueprints upload -a $blueprint
    fi
  done
fi
