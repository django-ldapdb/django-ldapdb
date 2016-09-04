# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from django.conf import settings
import sys

import ldap.filter


def escape_ldap_filter(value):
    if sys.version_info[0] < 3:
        text_value = unicode(value)
    else:
        text_value = str(value)
    return ldap.filter.escape_filter_chars(text_value)

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
