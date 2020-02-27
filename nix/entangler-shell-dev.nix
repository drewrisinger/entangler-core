{ pkgs ? import <nixpkgs> {}
, artiqpkgs ? import <artiq-full> {}
}:

# Use this shell to build the Gateware for the Entangler.
# Adds the Entangler package to ARTIQ's default "shell-dev.nix" environment

# Can be called like ``$ nix-shell -I artiqSrc=/PATH/TO/ARTIQ/GIT/REPO ./entangler-shell-dev.nix``
# TODO: remove dependency on <artiqSrc>. Can't figure out how to easily remove, other than maybe patch.

let
  entangler = pkgs.callPackage ./default.nix { inherit artiqpkgs; };
  mlabs-nix-scripts = builtins.fetchGit {
    url="https://git.m-labs.hk/M-Labs/nix-scripts.git";
    ref="master"; # impure, but fine for our purposes
  };
  dev-artiq-shell = import "${mlabs-nix-scripts}/artiq-fast/shell-dev.nix" {};  # Depends on <artiqSrc> to import, can't remove artiqSrc dependency easily. moving on.
  # Force shell to use Release (i.e. MLabs Nix Channel) ARTIQ build, instead of passing all source/arguments ourselves.
  dev-shell-with-release-artiq = dev-artiq-shell.overrideAttrs (oldAttrs: rec { artiqpkgs = artiqpkgs ; });
in
  pkgs.mkShell{
    # Add Entangler to the development shell
    buildInputs = [ entangler ] ++ dev-shell-with-release-artiq.buildInputs;
    inherit (dev-shell-with-release-artiq) TARGET_AR;  # Set LLVM target
  }
