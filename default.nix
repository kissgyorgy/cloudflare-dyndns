# This file provides a derivation for use with legacy nix (non-flake)
# Usage: nix-build
{ pkgs ? import <nixpkgs> {} }:

let
  lib = pkgs.lib;
  meta = (import ./meta.nix) lib;
in

with pkgs.python312Packages;
buildPythonApplication {
  pname = meta.name;
  version = meta.version;
  pyproject = true;
  src = ./.;
  dependencies = map (name: pkgs.python312Packages.${name}) meta.dependencies;
  build-system = [ hatchling ];
  meta.mainProgram = meta.mainProgram;
}
