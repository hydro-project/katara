#!/usr/bin/env bash

cur_dir=$(pwd)

paths_to_save=$(nix-store --query --references $(nix path-info --derivation ".#devShell.x86_64-linux.inputDerivation") | \
  xargs nix-store --realise | \
  xargs nix-store --query --requisites)

mkdir ~/nix-cache

cd ~/nix-cache

nix-store --export $paths_to_save > ~/nix-cache/cache.nar

cd $cur_dir
