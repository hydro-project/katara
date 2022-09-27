let
  # updated 9/27/22
  pkgs = import (fetchTarball https://github.com/nixos/nixpkgs/archive/82379884b2e9cf1ba65f5b14bbcb9d1438abb745.tar.gz) { };
  unstable = import (fetchTarball https://github.com/NixOS/nixpkgs/archive/4dd035239719fc7992a4214934ecaf2a943d5ec0.tar.gz) { };
  poetry2nixLatest = import (fetchTarball https://github.com/NixOS/nixpkgs/archive/2a2193eb0677a8801c3b414f67bacf499bd0b6fc.tar.gz) { };
in
with pkgs;

(poetry2nixLatest.poetry2nix.mkPoetryEnv {
  python = python38;
  projectDir = ./.;
  preferWheels = true;

  editablePackageSources = {
    metalift = ./metalift;
  };
}).env.overrideAttrs(old: {
  buildInputs = [
    unstable.cvc5
    cmake
    llvm_11
    clang_11
  ];

  hardeningDisable = [ "fortify" ];
})
