{ pkgs ? import <nixpkgs> {} }:

# To run this package in development mode (where code changes are reflected in shell w/o restart),
# run this Nix shell by itself. It lacks some of the packages needed to build a full ARTIQ
# bootloader/gateware file, but it's good for testing internal stuff.
# i.e. ``nix-shell ./default.nix``


let
  entangler-src = ./..;
  entangler-deps = pkgs.callPackage ./entangler-dependencies.nix {};

  artiq = pkgs.callPackage <artiq-full> {};
  # patch exposes peripheral processors dict. Not needed in future versions of ARTIQ, probably. Can remove next few lines then
  patched-artiq = artiq.artiq.overrideAttrs (oldAttrs: rec {
    patches = (oldAttrs.patches or []) ++ ["${entangler-src}/kasli_generic-expose-peripheral_processors-dict.patch"];
  });
in
  pkgs.python3Packages.buildPythonPackage rec {
    pname = "entangler";
    version = "0.2";
    src = entangler-src;
    buildInputs = with pkgs.python3Packages; [pytestrunner];
    propagatedBuildInputs = [
      patched-artiq
      entangler-deps.dynaconf
      artiq.migen
      artiq.misoc
      pkgs.python3Packages.setuptools # setuptools needed for ``import pkg_resources`` to find settings.toml
    ];
    doCheck = false;
    pythonImportsCheck = [ "${pname}" "${pname}.kasli_generic" "${pname}.driver" "${pname}.phy" ];
  }
