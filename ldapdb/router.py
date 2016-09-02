# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project


def is_ldap_model(model):
    # FIXME: there is probably a better check than testing 'base_dn'
    return hasattr(model, 'base_dn')


class Router(object):
    """
    A router to point database operations on LDAP models to the LDAP
    database.

    NOTE: if you have more than one LDAP database, you will need to
    write your own router.
    """

    def __init__(self):
        "Find the name of the LDAP database"
        from django.conf import settings
        self.ldap_alias = None
        for alias, settings_dict in settings.DATABASES.items():
            if settings_dict['ENGINE'] == 'ldapdb.backends.ldap':
                self.ldap_alias = alias
                break

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if 'model' in hints and is_ldap_model(hints['model']):
            return False
        return None

    def db_for_read(self, model, **hints):
        "Point all operations on LDAP models to the LDAP database"
        if is_ldap_model(model):
            return self.ldap_alias
        return None

    def db_for_write(self, model, **hints):
        "Point all operations on LDAP models to the LDAP database"
        if is_ldap_model(model):
            return self.ldap_alias
        return None
