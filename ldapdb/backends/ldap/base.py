# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import ldap
import ldap.controls
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.client import BaseDatabaseClient
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.base.features import BaseDatabaseFeatures
from django.db.backends.base.introspection import BaseDatabaseIntrospection
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.base.validation import BaseDatabaseValidation


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
    can_use_chunked_reads = False
    supports_transactions = False

    def __init__(self, connection):
        self.connection = connection


class DatabaseIntrospection(BaseDatabaseIntrospection):
    def get_table_list(self, cursor):
        return []


class DatabaseOperations(BaseDatabaseOperations):
    compiler_module = "ldapdb.backends.ldap.compiler"

    def quote_name(self, name):
        return name

    def no_limit_value(self):
        return -1


class DatabaseValidation(BaseDatabaseValidation):
    pass


class LdapDatabase(object):
    # Base class for all exceptions
    Error = ldap.LDAPError

    class DatabaseError(Error):
        """Database-side errors."""

    class OperationalError(
            DatabaseError,
            ldap.ADMINLIMIT_EXCEEDED,
            ldap.AUTH_METHOD_NOT_SUPPORTED,
            ldap.AUTH_UNKNOWN,
            ldap.BUSY,
            ldap.CONFIDENTIALITY_REQUIRED,
            ldap.CONNECT_ERROR,
            ldap.INAPPROPRIATE_AUTH,
            ldap.INVALID_CREDENTIALS,
            ldap.OPERATIONS_ERROR,
            ldap.RESULTS_TOO_LARGE,
            ldap.SASL_BIND_IN_PROGRESS,
            ldap.SERVER_DOWN,
            ldap.SIZELIMIT_EXCEEDED,
            ldap.STRONG_AUTH_NOT_SUPPORTED,
            ldap.STRONG_AUTH_REQUIRED,
            ldap.TIMELIMIT_EXCEEDED,
            ldap.TIMEOUT,
            ldap.UNAVAILABLE,
            ldap.UNAVAILABLE_CRITICAL_EXTENSION,
            ldap.UNWILLING_TO_PERFORM,
    ):
        """Exceptions related to the database operations, out of the programmer control."""

    class IntegrityError(
            DatabaseError,
            ldap.AFFECTS_MULTIPLE_DSAS,
            ldap.ALREADY_EXISTS,
            ldap.CONSTRAINT_VIOLATION,
            ldap.TYPE_OR_VALUE_EXISTS,
    ):
        """Exceptions related to database Integrity."""

    class DataError(
            DatabaseError,
            ldap.INVALID_DN_SYNTAX,
            ldap.INVALID_SYNTAX,
            ldap.NOT_ALLOWED_ON_NONLEAF,
            ldap.NOT_ALLOWED_ON_RDN,
            ldap.OBJECT_CLASS_VIOLATION,
            ldap.UNDEFINED_TYPE,
    ):
        """Exceptions related to invalid data"""

    class InterfaceError(
            ldap.CLIENT_LOOP,
            ldap.DECODING_ERROR,
            ldap.ENCODING_ERROR,
            ldap.LOCAL_ERROR,
            ldap.LOOP_DETECT,
            ldap.NO_MEMORY,
            ldap.PROTOCOL_ERROR,
            ldap.REFERRAL_LIMIT_EXCEEDED,
            ldap.USER_CANCELLED,
            Error,
    ):
        """Exceptions related to the pyldap interface."""

    class InternalError(
            DatabaseError,
            ldap.ALIAS_DEREF_PROBLEM,
            ldap.ALIAS_PROBLEM,
    ):
        """Exceptions encountered within the database."""

    class ProgrammingError(
            DatabaseError,
            ldap.CONTROL_NOT_FOUND,
            ldap.FILTER_ERROR,
            ldap.INAPPROPRIATE_MATCHING,
            ldap.NAMING_VIOLATION,
            ldap.NO_SUCH_ATTRIBUTE,
            ldap.NO_SUCH_OBJECT,
            ldap.PARAM_ERROR,
    ):
        """Invalid data send by the programmer."""

    class NotSupportedError(
            DatabaseError,
            ldap.NOT_SUPPORTED,
    ):
        """Exception for unsupported actions."""


class LdapSchemaEditor(BaseDatabaseSchemaEditor):
    def create_model(self, cursor):
        pass


class LdapClient(BaseDatabaseClient):
    executable_name = 'ldapsearch'


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'ldap'

    Database = LdapDatabase
    SchemaEditorClass = LdapSchemaEditor

    # Hook for sibling classes
    client_class = LdapClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations
    validation_class = DatabaseValidation

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

        self.settings_dict['SUPPORTS_TRANSACTIONS'] = True
        self.autocommit = True
        # Default page size of 1000 items, ActiveDirectory's default
        # See https://support.microsoft.com/en-us/help/315071/how-to-view-and-set-ldap-policy-in-active-directory-by-using-ntdsutil.exe  # noqa
        self.page_size = 1000

    def close(self):
        if hasattr(self, 'validate_thread_sharing'):
            # django >= 1.4
            self.validate_thread_sharing()
        if self.connection is not None:
            self.connection.unbind_s()
            self.connection = None

    def get_connection_params(self):
        """Compute appropriate parameters for establishing a new connection.

        Computed at system startup.
        """
        return {
            'uri': self.settings_dict['NAME'],
            'tls': self.settings_dict.get('TLS', False),
            'bind_dn': self.settings_dict['USER'],
            'bind_pw': self.settings_dict['PASSWORD'],
            'options': {
                k if isinstance(k, int) else k.lower(): v
                for k, v in self.settings_dict.get('CONNECTION_OPTIONS', {}).items()
            },
        }

    def get_new_connection(self, conn_params):
        """Build a connection from its parameters."""
        connection = ldap.initialize(conn_params['uri'], bytes_mode=False)

        options = conn_params['options']
        for opt, value in options.items():
            if opt == 'query_timeout':
                connection.timeout = int(value)
            elif opt == 'page_size':
                self.page_size = int(value)
            else:
                connection.set_option(opt, value)

        if conn_params['tls']:
            connection.start_tls_s()

        connection.simple_bind_s(
            conn_params['bind_dn'],
            conn_params['bind_pw'],
        )
        return connection

    def init_connection_state(self):
        """Initialize python-side connection state."""
        pass

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

    def search_s(self, base, scope, filterstr='(objectClass=*)', attrlist=None):
        cursor = self._cursor()
        query_timeout = cursor.connection.timeout

        # Request pagination; don't fail if the server doesn't support it.
        ldap_control = ldap.controls.SimplePagedResultsControl(
            criticality=False,
            size=self.page_size,
            cookie='',
        )

        # Fetch results
        page = 0

        while True:
            msgid = cursor.connection.search_ext(
                base=base,
                scope=scope,
                filterstr=filterstr,
                attrlist=attrlist,
                serverctrls=[ldap_control],
                timeout=query_timeout,
            )

            _res_type, results, _res_msgid, server_controls = cursor.connection.result3(msgid, timeout=query_timeout)
            page_controls = [ctrl for ctrl in server_controls if ctrl.controlType == ldap.CONTROL_PAGEDRESULTS]

            for dn, attrs in results:
                # skip referrals
                if dn is not None:
                    yield dn, attrs

            page_control = page_controls[0]
            page += 1
            if page_control.cookie:
                ldap_control.cookie = page_control.cookie
            else:
                # End of pages
                break
