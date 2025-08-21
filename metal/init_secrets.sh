#!/bin/bash

cluster_name=$(yq -r '.cluster_name' vars.yaml)
cluster_endpoint=$(yq -r '.cluster_endpoint' vars.yaml)

if ! [ -f "secrets.yaml" ]; then
  talosctl gen secrets -o secrets.yaml
else
  echo secrets.yaml already exists
fi

if ! [ -f "talosconfig" ]; then
  talosctl gen config $cluster_name $cluster_endpoint --with-secrets secrets.yaml -t talosconfig
else
  echo talosconfig already exists
fi
