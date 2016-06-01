# -*- coding: utf-8 -*-
#
# django-ldapdb
# Copyright (c) 2009-2011, Bolloré telecom
# Copyright (c) 2013, Jeremy Lainé
# All rights reserved.
#
# See AUTHORS file for a full list of contributors.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright notice,
#        this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import unicode_literals

import ldap
import django

if django.VERSION < (1, 8):
    from django.db.backends import (BaseDatabaseFeatures, BaseDatabaseOperations,
                                    BaseDatabaseWrapper)
    from django.db.backends.creation import BaseDatabaseCreation
else:
    from django.db.backends.base.features import BaseDatabaseFeatures
    from django.db.backends.base.operations import BaseDatabaseOperations
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.creation import BaseDatabaseCreation


class DatabaseCreation(BaseDatabaseCreation):
    def create_test_db(self, *args, **kwargs):
        """
        Creates a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        pass

    def destroy_test_db(self, *args, **kwargs):
        """
        Destroy a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        pass


class DatabaseCursor(object):
    def __init__(self, ldap_connection):
        self.connection = ldap_connection


class DatabaseFeatures(BaseDatabaseFeatures):
    def __init__(self, connection):
        self.connection = connection
        self.supports_transactions = False


class DatabaseOperations(BaseDatabaseOperations):
    compiler_module = "ldapdb.backends.ldap.compiler"

    def quote_name(self, name):
        return name

    def no_limit_value(self):
        return -1


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'ldap'

    # NOTE: These are copied from the mysql DatabaseWrapper
    operators = {
        'exact': '= %s',
        'iexact': 'LIKE %s',
        'contains': 'LIKE BINARY %s',
        'icontains': 'LIKE %s',
        'regex': 'REGEXP BINARY %s',
        'iregex': 'REGEXP %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE BINARY %s',
        'endswith': 'LIKE BINARY %s',
        'istartswith': 'LIKE %s',
        'iendswith': 'LIKE %s',
    }

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)

        # Charset used for LDAP text *values*
        self.charset = "utf-8"
        self.creation = DatabaseCreation(self)
        self.features = DatabaseFeatures(self)
        if django.VERSION > (1, 4):
            self.ops = DatabaseOperations(self)
        else:
            self.ops = DatabaseOperations()
        self.settings_dict['SUPPORTS_TRANSACTIONS'] = True
        self.autocommit = True

    def close(self):
        if hasattr(self, 'validate_thread_sharing'):
            # django >= 1.4
            self.validate_thread_sharing()
        if self.connection is not None:
            self.connection.unbind_s()
            self.connection = None

    def ensure_connection(self):
        if self.connection is None:
            self.connection = ldap.initialize(self.settings_dict['NAME'], bytes_mode=False)

            options = self.settings_dict.get('CONNECTION_OPTIONS', {})
            for opt, value in options.items():
                self.connection.set_option(opt, value)

            if self.settings_dict.get('TLS', False):
                self.connection.start_tls_s()

            self.connection.simple_bind_s(
                self.settings_dict['USER'],
                self.settings_dict['PASSWORD'],
            )

    def _commit(self):
        pass

    def _cursor(self):
        self.ensure_connection()
        return DatabaseCursor(self.connection)

    def _rollback(self):
        pass

    def _set_autocommit(self, autocommit):
        pass

    def add_s(self, dn, modlist):
        cursor = self._cursor()
        return cursor.connection.add_s(dn, modlist)

    def delete_s(self, dn):
        cursor = self._cursor()
        return cursor.connection.delete_s(dn)

    def modify_s(self, dn, modlist):
        cursor = self._cursor()
        return cursor.connection.modify_s(dn, modlist)

    def rename_s(self, dn, newrdn):
        cursor = self._cursor()
        return cursor.connection.rename_s(dn, newrdn)

    def search_s(self, base, scope, filterstr='(objectClass=*)',
                 attrlist=None):
        cursor = self._cursor()
        results = cursor.connection.search_s(base, scope, filterstr, attrlist)
        output = []
        for dn, attrs in results:
            # skip referrals
            if dn is not None:
                output.append((dn, attrs))
        return output
