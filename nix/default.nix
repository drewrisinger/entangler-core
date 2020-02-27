{ pkgs ? import <nixpkgs> {}
, artiqpkgs ? import <artiq-full> {}
}:

# To run this package in development mode (where code changes are reflected in shell w/o restart),
# run this Nix shell by itself. It lacks some of the packages needed to build a full ARTIQ
# bootloader/gateware file, but it's good for testing internal stuff.
# i.e. ``nix-shell ./default.nix``


let
  entangler-src = ./..;
  entangler-deps = pkgs.callPackage ./entangler-dependencies.nix {};
in
  pkgs.python3Packages.buildPythonPackage rec {
    pname = "entangler";
    version = "1.1.1";

    src = entangler-src;

    buildInputs = with pkgs.python3Packages; [ pytestrunner ];

    propagatedBuildInputs = [
      artiqpkgs.artiq
      entangler-deps.dynaconf
      artiqpkgs.migen
      artiqpkgs.misoc
      pkgs.python3Packages.setuptools # setuptools needed for ``import pkg_resources`` to find settings.toml
    ];

    doCheck = true;
    checkInputs = [ pkgs.python3Packages.pytest ];
    checkPhase = ''
      pytest -m 'not slow'
    '';
    pythonImportsCheck = [ pname "${pname}.kasli_generic" "${pname}.driver" "${pname}.phy" ];

    meta = with pkgs.lib; {
      description = "ARTIQ extension to generate & check patterns (for entanglement).";
      homepage = "https://github.com/drewrisinger/entangler-core/";
      license = licenses.gpl3;
      platforms = platforms.all;
      maintainers = with maintainers; [ drewrisinger ];
    };
  }
