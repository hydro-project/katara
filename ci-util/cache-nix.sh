#!/usr/bin/env bash

cur_dir=$(pwd)

mkdir ~/nix-cache

cd ~/nix-cache

paths_to_save=$(nix-store --query --references $(nix-instantiate $cur_dir/ci-shell.nix) | \
  xargs nix-store --realise | \
  xargs nix-store --query --requisites)

nix-store --export $paths_to_save > ~/nix-cache/cache.nar

cd $cur_dir
