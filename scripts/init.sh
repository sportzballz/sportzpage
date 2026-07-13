#!/usr/bin/env bash
# scripts/init.sh
# Initialize the project for first use.
set -euo pipefail

mkdir -p build config

for tpl in config/settings.yaml config/editorial.yaml config/schedules.yaml config/teams.yaml; do
  if [ ! -f "$tpl" ]; then
    echo "WARNING: $tpl not found. Copy the example files from config/ to get started."
  fi
done

echo "Init complete. Edit config/*.yaml before running the pipeline."
