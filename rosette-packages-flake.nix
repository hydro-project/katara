# copy me to ../rosette-packages/flake.nix
# then run raco pkg install --scope-dir ../rosette-packages/packages rosette
{
  description = "rosette-packages";

  inputs = {};

  outputs = { self }: {
    packages = ./packages;
  };
}
