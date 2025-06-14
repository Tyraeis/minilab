#!/bin/bash

if [ -f "secrets.yaml" ]; then
  echo "Error: secrets.yaml already exists"
  exit 1
fi

cluster_name=$(yq -r '.cluster_name' vars.yaml)
cluster_endpoint=https://$(yq -r '.virtual_ip' vars.yaml):6443

talosctl gen secrets -o secrets.yaml
talosctl gen config $cluster_name $cluster_endpoint --with-secrets secrets.yaml -t talosconfig
