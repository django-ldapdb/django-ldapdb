# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

from django.db.models import fields, SubfieldBase

from ldapdb import escape_ldap_filter

import datetime


class CharField(fields.CharField):
    def __init__(self, *args, **kwargs):
        defaults = {'max_length': 200}
        defaults.update(kwargs)
        super(CharField, self).__init__(*args, **defaults)

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return ''
        else:
            return value[0].decode(connection.charset)

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        if lookup_type == 'endswith':
            return ["*%s" % escape_ldap_filter(value)]
        elif lookup_type == 'startswith':
            return ["%s*" % escape_ldap_filter(value)]
        elif lookup_type in ['contains', 'icontains']:
            return ["*%s*" % escape_ldap_filter(value)]
        elif lookup_type == 'exact':
            return [escape_ldap_filter(value)]
        elif lookup_type == 'in':
            return [escape_ldap_filter(v) for v in value]

        raise TypeError("CharField has invalid lookup: %s" % lookup_type)

    def get_db_prep_save(self, value, connection):
        if not value:
            return None
        return [value.encode(connection.charset)]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        if lookup_type == 'endswith':
            return "*%s" % escape_ldap_filter(value)
        elif lookup_type == 'startswith':
            return "%s*" % escape_ldap_filter(value)
        elif lookup_type in ['contains', 'icontains']:
            return "*%s*" % escape_ldap_filter(value)
        elif lookup_type == 'exact':
            return escape_ldap_filter(value)
        elif lookup_type == 'in':
            return [escape_ldap_filter(v) for v in value]

        raise TypeError("CharField has invalid lookup: %s" % lookup_type)


class ImageField(fields.Field):
    def from_ldap(self, value, connection):
        if len(value) == 0:
            return ''
        else:
            return value[0]

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        return [self.get_prep_lookup(lookup_type, value)]

    def get_db_prep_save(self, value, connection):
        if not value:
            return None
        return [value]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        raise TypeError("ImageField has invalid lookup: %s" % lookup_type)


class IntegerField(fields.IntegerField):
    def from_ldap(self, value, connection):
        if len(value) == 0:
            return 0
        else:
            return int(value[0])

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        return [self.get_prep_lookup(lookup_type, value)]

    def get_db_prep_save(self, value, connection):
        if value is None:
            return None
        return [str(value).encode(connection.charset)]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        if lookup_type in ('exact', 'gte', 'lte'):
            return value
        raise TypeError("IntegerField has invalid lookup: %s" % lookup_type)


class FloatField(fields.FloatField):
    def from_ldap(self, value, connection):
        if len(value) == 0:
            return 0.0
        else:
            return float(value[0])

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        return [self.get_prep_lookup(lookup_type, value)]

    def get_db_prep_save(self, value, connection):
        if value is None:
            return None
        return [str(value).encode(connection.charset)]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        if lookup_type in ('exact', 'gte', 'lte'):
            return value
        raise TypeError("FloatField has invalid lookup: %s" % lookup_type)


class ListField(fields.Field):
    __metaclass__ = SubfieldBase

    def from_ldap(self, value, connection):
        return [x.decode(connection.charset) for x in value]

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        return [self.get_prep_lookup(lookup_type, value)]

    def get_db_prep_save(self, value, connection):
        if not value:
            return None
        return [x.encode(connection.charset) for x in value]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        if lookup_type == 'contains':
            return escape_ldap_filter(value)
        raise TypeError("ListField has invalid lookup: %s" % lookup_type)

    def to_python(self, value):
        if not value:
            return []
        return value


class DateField(fields.DateField):
    """
    A text field containing date, in specified format.
    The format can be specified as 'format' argument, as strptime()
    format string. It defaults to ISO8601 (%Y-%m-%d).

    Note: 'lte' and 'gte' lookups are done string-wise. Therefore,
    they will onlywork correctly on Y-m-d dates with constant
    component widths.
    """

    def __init__(self, *args, **kwargs):
        if 'format' in kwargs:
            self._date_format = kwargs.pop('format')
        else:
            self._date_format = '%Y-%m-%d'
        super(DateField, self).__init__(*args, **kwargs)

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return None
        else:
            return datetime.datetime.strptime(value[0],
                                              self._date_format).date()

    def get_db_prep_lookup(self, lookup_type, value, connection,
                           prepared=False):
        "Returns field's value prepared for database lookup."
        return [self.get_prep_lookup(lookup_type, value)]

    def get_db_prep_save(self, value, connection):
        if not value:
            return None
        if not isinstance(value, datetime.date) \
                and not isinstance(value, datetime.datetime):
            raise ValueError(
                'DateField can be only set to a datetime.date instance')

        return [value.strftime(self._date_format)]

    def get_prep_lookup(self, lookup_type, value):
        "Perform preliminary non-db specific lookup checks and conversions"
        if lookup_type in ('exact',):
            return value
        raise TypeError("DateField has invalid lookup: %s" % lookup_type)
