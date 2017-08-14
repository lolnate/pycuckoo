#!/usr/bin/env python

import sys

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

description = "Python library for using the Cuckoo 2.0 API".encode('utf-8')

install_requires = []
# For Python < 2.7.9, requests[security] is needed which installs extra
# packages for more secure connections. Python >= 2.7.9 doesn't need this.
if (sys.version_info[0] == 3 or
    (sys.version_info[0] == 2 and
     sys.version_info[1] == 7 and
     sys.version_info[2] >= 9)):
    install_requires.append('requests')
else:
    install_requires.append('requests[security]')

setup(
    name="pycuckoo",
    version="0.1",
    description='Python interface to the Cuckoo API',
    long_description=long_description,
    author="Nate Hausrath",
    author_email="nate@alien.pizza",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
    ],
    license="Apache 2.0",
    keywords="cuckoo",
    url="https://github.com/lolnate/pycuckoo",
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=install_requires
)
