"""Install the ``entangler`` package for use in ARTIQ.

You can install this package locally (in development mode) using:
``$ pip install -e .``.
"""
import setuptools

if __name__ == "__main__":
    setuptools.setup(
        name="entangler",
        version="0.1",
        packages=setuptools.find_packages(),
        requirements=["artiq>=5", "dynaconf", "migen", "numpy"],
        url="https://github.com/drewrisinger/entangler-core",
        setup_requires=["pytest-runner"],
        tests_require=["pytest"],
        package_data={
            "": ["*.txt", "*.toml", "*.md"],
        }
    )
