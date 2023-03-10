{ config, options, lib, pkgs, specialArgs, ... }:

lib.mkMerge [{
  environment.systemPackages = with pkgs; [
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
    gnumake
    cmake
    llvm_11
    llvm_11.dev
    clang_11

    racket

    htop
    nano
    vim
    emacs
  ];

  users = {
    mutableUsers = false;
    allowNoPasswordLogin = true;

    users = {
      demo = {
        home = "/home/demo";
        password = "demo";
        extraGroups = [ "wheel" ];
        isNormalUser = true;
      };
    };
  };

  security.sudo.wheelNeedsPassword = false;

  boot.postBootCommands = let source =
    let
      inherit (specialArgs.gitignore.lib) gitignoreSource;
    in pkgs.lib.cleanSourceWith
      { filter = (path: type:
          ! (builtins.any
            (r: (builtins.match r (builtins.baseNameOf path)) != null)
            [])
        );
        src = gitignoreSource ./.;
      } ;
  in ''
    echo "Loading source code for the artifact"

    ${pkgs.rsync}/bin/rsync -r --owner --group --chown=demo:users --perms --chmod=u+rw ${source}/ /home/demo

    mkdir -p /home/demo/.racket/8.7/pkgs
    ln -s ${./iso-racket-links.rktd} /home/demo/.racket/8.7/links.rktd
    ln -s ${specialArgs.rosette-packages.packages}/* /home/demo/.racket/8.7/pkgs/

    rm /home/demo/.racket/8.7/pkgs/rosette
    ${pkgs.rsync}/bin/rsync -r --owner --group --chown=demo:users --perms --chmod=u+rw ${specialArgs.rosette-packages.packages}/rosette/ /home/demo/.racket/8.7/pkgs/rosette
    mkdir /home/demo/.racket/8.7/pkgs/rosette/bin
    ln -s ${(pkgs.z3.overrideAttrs(self: {
      version = "4.8.8";

      src = pkgs.fetchFromGitHub {
        owner = "Z3Prover";
        repo = "z3";
        rev = "z3-4.8.8";
        hash = "sha256-qpmi75I27m89dhKSy8D2zkzqKpLoFBPRBrhzDB8axeY=";
      };
    }))}/bin/z3 /home/demo/.racket/8.7/pkgs/rosette/bin/z3
  '';

  services.getty.autologinUser = "demo";

  services.openssh.enable = true;
  networking.firewall.allowedTCPPorts = [ 22 ];

  services.xserver.enable = true;
} (lib.optionalAttrs (builtins.hasAttr "isoImage" options) {
  isoImage.appendToMenuLabel = " OOPSLA CRDT Synthesis Artifact";
  services.xserver.displayManager.startx.enable = true;
}) (lib.optionalAttrs (builtins.hasAttr "virtualbox" options) {
  nixpkgs.config = {
    allowUnfree = true;
  };

  virtualbox.vmName = "OOPSLA CRDT Synthesis Artifact";
  virtualbox.memorySize = 1024 * 8;
  virtualbox.params.cpus = 8;
  virtualbox.params.usb = "off";
  virtualbox.params.usbehci = "off";

  services.xserver.desktopManager.gnome.enable = true;
  services.xserver.displayManager.lightdm.enable = true;

  services.getty.autologinUser = pkgs.lib.mkForce null;

  environment.systemPackages = with pkgs; [
    vscode
    sublime
    firefox
  ];
})]
