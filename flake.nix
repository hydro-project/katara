{
  description = "katara";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.11";
  inputs.poetry2nix-flake = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  inputs.nixos-generators = {
    url = "github:nix-community/nixos-generators";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  inputs.gitignore = {
    url = "github:hercules-ci/gitignore.nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  inputs.rosette-packages.url = "github:input-output-hk/empty-flake?rev=2040a05b67bf9a669ce17eca56beb14b4206a99a";

  outputs = { self, nixpkgs, flake-utils, poetry2nix-flake, nixos-generators, gitignore, rosette-packages }: (flake-utils.lib.eachDefaultSystem (system:
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
  )) // {
    packages.x86_64-linux = {
      # nix build .#vm-nogui --override-input rosette-packages ../rosette-packages
      vm-nogui = nixos-generators.nixosGenerate {
        system = "x86_64-linux";
        modules = [
          ({ pkgs, ... }: {
            nixpkgs.overlays = [ poetry2nix-flake.overlay ];
          })
          ./artifact.nix
        ];
        format = "vm-nogui";
        
        specialArgs = {
          gitignore = gitignore;
          rosette-packages = rosette-packages;
        };
      };
    };
  };
}
