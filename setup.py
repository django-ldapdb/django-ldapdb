#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import codecs
import os
import re
import sys

from setuptools import find_packages, setup

root_dir = os.path.abspath(os.path.dirname(__file__))


def get_version(package_name):
    version_re = re.compile(r"^VERSION = [\"']([\w_.-]+)[\"']$")
    package_components = package_name.split('.')
    init_path = os.path.join(root_dir, *(package_components + ['version.py']))
    with codecs.open(init_path, 'r', 'utf-8') as f:
        for line in f:
            match = version_re.match(line[:-1])
            if match:
                return match.groups()[0]
    return '0.1.0'


PACKAGE = 'django-ldapdb-ugent'
PYPACKAGE = 'ldapdb'


setup(
    name=PACKAGE,
    version=get_version(PYPACKAGE),
    description="An LDAP database backend for Django",
    long_description=''.join(codecs.open('README.rst', 'r', 'utf-8').readlines()),
    author="Jeremy Laine",
    author_email="jeremy.laine@m4x.org",
    maintainer="Raphaël Barrois",
    maintainer_email="raphael.barrois+%s@polytechnique.org" % PACKAGE,
    license="BSD",
    keywords=['django', 'ldap', 'database'],
    url="https://github.com/UGentPortaal/django-ldapdb-ugent",
    packages=find_packages(exclude=['tests*', 'examples*']),
    install_requires=[
        'Django>=1.8',
        'pyldap-ugent>=2.4.28',
    ],
    setup_requires=[
        'setuptools>=0.8',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: System :: Systems Administration :: Authentication/Directory :: LDAP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    test_suite = 'manage_dev.run_tests'
)
