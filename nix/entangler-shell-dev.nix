{pkgs ? import <nixpkgs> {}}:

# Use this shell to build the Gateware for the Entangler.
# Adds the Entangler package to ARTIQ's default "shell-dev.nix" environment

# Can be called like ``$ nix-shell -I artiqSrc=/PATH/TO/ARTIQ/GIT/REPO ./entangler-shell-dev.nix``
# TODO: remove dependency on artiqSrc

let
  entangler = pkgs.callPackage ./default.nix {};
  mlabs-nix-scripts = builtins.fetchGit {
    url="https://git.m-labs.hk/M-Labs/nix-scripts.git";
    ref="master"; # impure, but fine for our purposes
  };
  dev-artiq-shell = pkgs.callPackage "${mlabs-nix-scripts}/artiq-fast/shell-dev.nix" {};  # Depends on artiqSrc
  # Force shell to use Release (i.e. MLabs Nix Channel) ARTIQ build, instead of passing all source/arguments ourselves.
  dev-shell-with-release-artiq = dev-artiq-shell.overrideAttrs (oldAttrs: rec {artiqpkgs = pkgs.callPackage <artiq-full> {}; });
in
  pkgs.mkShell{
    # Add Entangler to the development shell
    buildInputs = [ entangler ] ++ dev-shell-with-release-artiq.buildInputs;
    # Set LLVM target
    TARGET_AR=dev-shell-with-release-artiq.TARGET_AR;
  }
