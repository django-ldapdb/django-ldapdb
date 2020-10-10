# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project


import ldap.filter
from django.conf import settings

from .version import __version__  # noqa


def escape_ldap_filter(value):
    return ldap.filter.escape_filter_chars(str(value))


# Legacy single database support
if hasattr(settings, 'LDAPDB_SERVER_URI'):
    from django import db

    from ldapdb.router import Router

    # Add the LDAP backend
    settings.DATABASES['ldap'] = {
        'ENGINE': 'ldapdb.backends.ldap',
        'NAME': settings.LDAPDB_SERVER_URI,
        'USER': settings.LDAPDB_BIND_DN,
        'PASSWORD': settings.LDAPDB_BIND_PASSWORD}

    # Add the LDAP router
    db.router.routers.append(Router())
