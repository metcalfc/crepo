#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="crepo",
    version='0.1.7',
    url="http://github.com/cloudera/crepo/tree/master",
    maintainer="Chad Metcalf",
    maintainer_email="chad@cloudera.com",
    py_modules=['crepo', 'git_command', 'git_repo', 'manifest', 'trace', 'test' ],
    entry_points = { 'console_scripts': [ 'crepo = crepo:main', ], },
    data_files=[('shell-tests', ['shell-tests/basic_test.sh', 'shell-tests/follow_tag.sh', 'shell-tests/smoke_test.sh']),],
    install_requires = ['setuptools', 'simplejson'],
)
