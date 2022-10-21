{
  description = "katara";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix-flake = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix-flake }: (flake-utils.lib.eachDefaultSystem (system:
    with import nixpkgs {
      inherit system;
      overlays = [ poetry2nix-flake.overlay ];
    };

    {
      devShell = mkShell {
        buildInputs = [
          (poetry2nix.mkPoetryEnv {
            python = python38;
            projectDir = ./.;

            overrides = poetry2nix.overrides.withDefaults (_: poetrySuper: {
              metalift = poetrySuper.metalift.overrideAttrs(_: super: {
                nativeBuildInputs = super.nativeBuildInputs ++ [ poetrySuper.poetry ];
              });

              autoflake = poetrySuper.autoflake.overrideAttrs(_: super: {
                nativeBuildInputs = super.nativeBuildInputs ++ [ poetrySuper.hatchling ];
              });
            });
          })

          cvc5
          cmake
          llvm_11
          clang_11
        ];
      };
    }
  ));
}
