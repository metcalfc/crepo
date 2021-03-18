#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="crepo",
    version='0.2.0',
    url="http://github.com/metcalfc/crepo/tree/main",
    maintainer="Chad Metcalf",
    maintainer_email="metcalfc@gmail.com",
    py_modules=['crepo', 'git_command', 'git_repo', 'manifest', 'test' ],
    entry_points = { 'console_scripts': [ 'crepo = crepo:main', ], },
    install_requires = ['setuptools', 'simplejson'],
)
