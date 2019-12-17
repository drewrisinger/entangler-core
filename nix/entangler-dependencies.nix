{ python3Packages, stdenv, fetchurl }:

rec {
  dynaconf = python3Packages.buildPythonPackage {
    pname = "dynaconf";
    version = "2.2.1";
    src = fetchurl {
      url = "https://files.pythonhosted.org/packages/ff/01/8870af63564d6aa3188ea43a9c1be32d3e79a3bd3b8d3872554534eeed6c/dynaconf-2.2.1.tar.gz";
      sha256 = "75691e9dd4093a1a2dc530d33369ae9296cfba30d29b72b00715dfb98b3f82e4";
    };
    doCheck = false;
    buildInputs = [ ];
    propagatedBuildInputs = with python3Packages; [
      click
      python-box
      python-dotenv
      toml
    ];
    meta = with stdenv.lib; {
      homepage = "https://github.com/rochacbruno/dynaconf";
      license = licenses.mit;
      description = "The dynamic configurator for your Python Project";
    };
  };

  python-box = python3Packages.buildPythonPackage {
    pname = "python-box";
    version = "3.4.6";
    src = fetchurl {
      url = "https://files.pythonhosted.org/packages/2e/3b/dc8066015af4dfc2aeae6666d3a0764b31548dee67fc7ef6803341fc8d9a/python-box-3.4.6.tar.gz";
      sha256 = "694a7555e3ff9fbbce734bbaef3aad92b8e4ed0659d3ed04d56b6a0a0eff26a9";
    };
    doCheck = true;
    buildInputs = with python3Packages; [ pytestcov pytest pytestrunner ];
    propagatedBuildInputs = [ ];
    meta = with stdenv.lib; {
      homepage = "https://github.com/cdgriffith/Box";
      license = licenses.mit;
      description = "Advanced Python dictionaries with dot notation access";
    };
  };
}
