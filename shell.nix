let
  pkgs = import <nixpkgs> {};
  unstable = import <nixos-unstable> {};
  poetry2nixLatest = import (fetchTarball https://github.com/NixOS/nixpkgs/archive/2a2193eb0677a8801c3b414f67bacf499bd0b6fc.tar.gz) { };
in
with pkgs;

(poetry2nixLatest.poetry2nix.mkPoetryEnv {
  python = python38;
  projectDir = ./.;
  preferWheels = true;
  overrides = poetry2nix.overrides.withDefaults (self: super: {
    pyparsing = python38Packages.pyparsing;
    packaging = python38Packages.packaging;
    typing-extensions = python38Packages.typing-extensions;
    metalift = super.metalift.overridePythonAttrs (super: {
      buildInputs = super.buildInputs ++ [ python38Packages.poetry ];
    });
  });
}).env.overrideAttrs(old: {
  buildInputs = [
    unstable.cvc5
    llvm_11
    clang_11
  ];

  hardeningDisable = [ "fortify" ];

  NIX_LD_LIBRARY_PATH = lib.makeLibraryPath [
    stdenv.cc.cc
  ];

  NIX_LD = lib.fileContents "${stdenv.cc}/nix-support/dynamic-linker";
})
