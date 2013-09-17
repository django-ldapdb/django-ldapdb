#!/usr/bin/env python

from setuptools import setup

setup(
    name = "django-ldapdb",
    version = "0.1.0",
    #license = ldapdb.__license__,
    url = "http://opensource.bolloretelecom.eu/projects/django-ldapdb/",
    author = "Jeremy Laine",
    author_email = "jeremy.laine@bolloretelecom.eu",
    packages = ['ldapdb', 'ldapdb.backends', 'ldapdb.backends.ldap', 'ldapdb.models'],
    test_suite='tests.runtests.runtests',
    )
