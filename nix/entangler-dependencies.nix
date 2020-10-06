{ python3Packages, stdenv }:

rec {
  dynaconf = python3Packages.buildPythonPackage rec {
    pname = "dynaconf";
    version = "2.2.2";
    src = python3Packages.fetchPypi {
      inherit pname version;
      sha256 = "4bac78b432e090d8ed66f1c23fb32e03ca91a590bf0a51ac36137e0e45ac31ca";
    };

    propagatedBuildInputs = with python3Packages; [
      click
      python-box
      python-dotenv
      toml
    ];

    doCheck = false;

    meta = with stdenv.lib; {
      homepage = "https://github.com/rochacbruno/dynaconf";
      description = "The dynamic configurator for your Python Project";
      license = licenses.mit;
    };
  };

  python-box = python3Packages.buildPythonPackage rec {
    pname = "python-box";
    version = "3.4.6";

    src = python3Packages.fetchPypi {
      inherit pname version;
      sha256 = "694a7555e3ff9fbbce734bbaef3aad92b8e4ed0659d3ed04d56b6a0a0eff26a9";
    };

    propagatedBuildInputs = [ ];

    doCheck = true;
    checkInputs = with python3Packages; [ pytestcov pytest pytestrunner ];

    meta = with stdenv.lib; {
      homepage = "https://github.com/cdgriffith/Box";
      description = "Advanced Python dictionaries with dot notation access";
      license = licenses.mit;
    };
  };

  python-dotenv = python3Packages.buildPythonPackage rec {
    pname = "python-dotenv";
    version = "0.10.3";

    src = python3Packages.fetchPypi {
      inherit pname version;
      sha256 = "f157d71d5fec9d4bd5f51c82746b6344dffa680ee85217c123f4a0c8117c4544";
    };

    propagatedBuildInputs = with python3Packages; [ click ipython sh ];

    doCheck = true;
    checkInputs = with python3Packages; [ pytestCheckHook mock ];
    dontUseSetuptoolsCheck = true;
    pytestFlagsArray = [
      "--ignore=tests/test_cli.py"
    ];

    meta = with stdenv.lib; {
      homepage = "https://github.com/theskumar/python-dotenv";
      description = "Get and set values in your .env file in local and production servers.";
      license = licenses.bsd3;
    };
  };
}
