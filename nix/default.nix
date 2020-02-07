{ pkgs ? import <nixpkgs> {} }:

# To run this package in development mode (where code changes are reflected in shell w/o restart),
# run this Nix shell by itself. It lacks some of the packages needed to build a full ARTIQ
# bootloader/gateware file, but it's good for testing internal stuff.
# i.e. ``nix-shell ./default.nix``


let
  entangler-src = ./..;
  entangler-deps = pkgs.callPackage ./entangler-dependencies.nix {};

  artiq = pkgs.callPackage <artiq-full> {};
  patched-artiq = artiq.artiq.overrideAttrs (oldAttrs: rec {
    patches = (oldAttrs.patches or []) ++ [
      (
        # patch exposes peripheral processors dict. Not needed in future versions of ARTIQ, probably. Can remove next few lines then
        pkgs.fetchpatch {
          url = "https://github.com/m-labs/artiq/commit/52112d54f9c052159b88b78dc6bd712abd4f062c.patch";
          sha256 = "0zyzk1czr1s7kvpy0jcc2mp209s5pivrv9020q8bqnl4244hd4fi";
        }
      )
      (
        # forces comm_analyzer to analyze generic Wishbone PHY devices. So can observe the PHY transactions
        pkgs.fetchpatch {
          url = "https://patch-diff.githubusercontent.com/raw/m-labs/artiq/pull/1427.patch";
          sha256 = "1zzd9ghi880k64whkq94m9xyxcrvgl232r00ymmqks79gq6ymg0s";
        }
      )
    ];
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
    doCheck = true;
    checkInputs = [ pkgs.python3Packages.pytest ];
    checkPhase = ''
      pytest -m 'not slow'
    '';
    pythonImportsCheck = [ "${pname}" "${pname}.kasli_generic" "${pname}.driver" "${pname}.phy" ];
  }
