#!/usr/bin/env python3
from setuptools import find_packages, setup

try:
    from catkin_pkg.python_setup import generate_distutils_setup

    setup_args = generate_distutils_setup(
        packages=find_packages("src"),
        package_dir={"": "src"},
    )
except ImportError:
    # Keeps ordinary Python tooling usable outside a ROS installation.
    setup_args = {
        "name": "smartcar-autonomous-driving",
        "version": "0.3.0",
        "packages": find_packages("src"),
        "package_dir": {"": "src"},
    }

setup(**setup_args)
