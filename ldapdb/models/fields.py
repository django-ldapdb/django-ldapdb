# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import datetime
import re

from django.db.models import fields, lookups
from django.utils import timezone


class LdapLookup(lookups.Lookup):
    rhs_is_iterable = False
    LDAP_PLACEHOLDER = '%s'

    def _as_ldap(self, lhs):
        raise NotImplementedError()

    def process_lhs(self, compiler, connection):
        return (self.lhs.target.column, [])

    def as_sql(self, compiler, connection):
        # lhs: field name; lhs_params: []
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs_params = self.rhs if self.rhs_is_iterable else [self.rhs]

        params = lhs_params + rhs_params
        if self.rhs_is_iterable:
            # Convert (x__in=[a, b, c]) to |(x=a)(x=b)(x=c)
            return '|' + ''.join(['({})'.format(self._as_ldap(lhs))] * len(rhs_params)), params
        else:
            return self._as_ldap(lhs), params

    def get_prep_lookup(self):
        """
        Convert the Python value(s) used in the lookup to LDAP values.
        """

        field = self.lhs.output_field

        if self.rhs_is_iterable and not field.multi_valued_field:
            # self.rhs is an iterable, and the field expects single-valued options.
            return [field.get_prep_value(v) for v in self.rhs]
        else:
            # self.rhs is 'as multi-valued' as the field.
            return field.get_prep_value(self.rhs)


class ContainsLookup(LdapLookup):
    lookup_name = 'contains'

    def _as_ldap(self, lhs):
        return '%s=*%s*' % (lhs, self.LDAP_PLACEHOLDER)


class IContainsLookup(ContainsLookup):
    lookup_name = 'icontains'


class StartsWithLookup(LdapLookup):
    lookup_name = 'startswith'

    def _as_ldap(self, lhs):
        return '%s=%s*' % (lhs, self.LDAP_PLACEHOLDER)


class EndsWithLookup(LdapLookup):
    lookup_name = 'endswith'

    def _as_ldap(self, lhs):
        return '%s=*%s' % (lhs, self.LDAP_PLACEHOLDER)


class ExactLookup(LdapLookup):
    lookup_name = 'exact'

    def _as_ldap(self, lhs):
        return '%s=%s' % (lhs, self.LDAP_PLACEHOLDER)


class GteLookup(LdapLookup):
    lookup_name = 'gte'

    def _as_ldap(self, lhs):
        return '%s>=%s' % (lhs, self.LDAP_PLACEHOLDER)


class LteLookup(LdapLookup):
    lookup_name = 'lte'

    def _as_ldap(self, lhs):
        return '%s<=%s' % (lhs, self.LDAP_PLACEHOLDER)


class InLookup(LdapLookup):
    lookup_name = 'in'
    rhs_is_iterable = True

    def _as_ldap(self, lhs):
        return '%s=%s' % (lhs, self.LDAP_PLACEHOLDER)


class ListContainsLookup(ExactLookup):
    lookup_name = 'contains'


class LdapFieldMixin(object):
    multi_valued_field = False
    binary_field = False

    def get_db_prep_value(self, value, connection, prepared=False):
        """Prepare a value for DB interaction.

        Returns:
        - list(bytes) if not prepared
        - list(str) if prepared
        """
        if prepared:
            return value

        if value is None:
            return []

        values = value if self.multi_valued_field else [value]
        prepared_values = [self.get_prep_value(v) for v in values]

        # Remove duplicates.
        # https://tools.ietf.org/html/rfc4511#section-4.1.7 :
        # "The set of attribute values is unordered."
        # We keep those values sorted in natural order to avoid useless
        # updates to the LDAP server.
        return list(sorted(set(v for v in prepared_values if v)))

    def get_db_prep_save(self, value, connection):
        values = self.get_db_prep_value(value, connection, prepared=False)
        if self.binary_field:
            # Already raw values; don't encode it twice.
            return values
        else:
            return [v.encode(connection.charset) for v in values]


class CharField(LdapFieldMixin, fields.CharField):
    def __init__(self, *args, **kwargs):
        defaults = {'max_length': 200}
        defaults.update(kwargs)
        super(CharField, self).__init__(*args, **defaults)

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return ''
        else:
            return value[0].decode(connection.charset)


CharField.register_lookup(ContainsLookup)
CharField.register_lookup(IContainsLookup)
CharField.register_lookup(StartsWithLookup)
CharField.register_lookup(EndsWithLookup)
CharField.register_lookup(InLookup)
CharField.register_lookup(ExactLookup)


class ImageField(LdapFieldMixin, fields.Field):
    binary_field = True

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return ''
        else:
            return value[0]


ImageField.register_lookup(ExactLookup)


class IntegerField(LdapFieldMixin, fields.IntegerField):
    def from_ldap(self, value, connection):
        if len(value) == 0:
            return None if self.null else 0
        else:
            return int(value[0])

    def get_prep_value(self, value):
        value = super(IntegerField, self).get_prep_value(value)
        return str(value)


IntegerField.register_lookup(ExactLookup)
IntegerField.register_lookup(GteLookup)
IntegerField.register_lookup(LteLookup)
IntegerField.register_lookup(InLookup)


class FloatField(LdapFieldMixin, fields.FloatField):
    def from_ldap(self, value, connection):
        if len(value) == 0:
            return None if self.null else 0.0
        else:
            return float(value[0])

    def get_prep_value(self, value):
        value = super(FloatField, self).get_prep_value(value)
        return str(value)


FloatField.register_lookup(ExactLookup)
FloatField.register_lookup(GteLookup)
FloatField.register_lookup(LteLookup)
FloatField.register_lookup(InLookup)


class ListField(LdapFieldMixin, fields.Field):

    multi_valued_field = True

    def from_ldap(self, value, connection):
        return [x.decode(connection.charset) for x in value]

    def from_db_value(self, value, expression, connection, context):
        """Convert from the database format.

        This should be the inverse of self.get_prep_value()
        """
        return self.to_python(value)

    def to_python(self, value):
        if not value:
            return []
        return value


ListField.register_lookup(ListContainsLookup)


class DateField(LdapFieldMixin, fields.DateField):
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
            return datetime.datetime.strptime(value[0].decode(connection.charset),
                                              self._date_format).date()

    def get_prep_value(self, value):
        value = super(DateField, self).get_prep_value(value)
        if not isinstance(value, datetime.date) \
                and not isinstance(value, datetime.datetime):
            raise ValueError(
                'DateField can be only set to a datetime.date instance; got {}'.format(repr(value)))

        return value.strftime(self._date_format)


DateField.register_lookup(ExactLookup)


LDAP_DATETIME_RE = re.compile(
    r'(?P<year>\d{4})'
    r'(?P<month>\d{2})'
    r'(?P<day>\d{2})'
    r'(?P<hour>\d{2})'
    r'(?P<minute>\d{2})?'
    r'(?P<second>\d{2})?'
    r'(?:[.,](?P<microsecond>\d+))?'
    r'(?P<tzinfo>Z|[+-]\d{2}(?:\d{2})?)'
    r'$'
)


LDAP_DATE_FORMAT = '%Y%m%d%H%M%S.%fZ'


def datetime_from_ldap(value):
    """Convert a LDAP-style datetime to a Python aware object.

    See https://tools.ietf.org/html/rfc4517#section-3.3.13 for details.

    Args:
        value (str): the datetime to parse
    """
    if not value:
        return None
    match = LDAP_DATETIME_RE.match(value)
    if not match:
        return None
    groups = match.groupdict()
    if groups['microsecond']:
        groups['microsecond'] = groups['microsecond'].ljust(6, '0')[:6]
    tzinfo = groups.pop('tzinfo')
    if tzinfo == 'Z':
        tzinfo = timezone.utc
    else:
        offset_mins = int(tzinfo[-2:]) if len(tzinfo) == 5 else 0
        offset = 60 * int(tzinfo[1:3]) + offset_mins
        if tzinfo[0] == '-':
            offset = - offset
        tzinfo = timezone.get_fixed_timezone(offset)
    kwargs = {k: int(v) for k, v in groups.items() if v is not None}
    kwargs['tzinfo'] = tzinfo
    return datetime.datetime(**kwargs)


class DateTimeField(LdapFieldMixin, fields.DateTimeField):
    """
    A field containing a UTC timestamp, in Generalized Time syntax.

    That syntax is ``YYYYmmddHH[MM[SS[.ff](Z|+XX[YY]|-XX[YY])``.

    See: https://tools.ietf.org/html/rfc4517#section-3.3.13
    """

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return None
        return datetime_from_ldap(value[0].decode(connection.charset))

    def get_prep_value(self, value):
        value = super(DateTimeField, self).get_prep_value(value)
        if not isinstance(value, datetime.date) \
                and not isinstance(value, datetime.datetime):
            raise ValueError(
                'DateTimeField can be only set to a datetime.datetime instance; got {}'.format(repr(value)))

        value = timezone.utc.normalize(value)
        return value.strftime(LDAP_DATE_FORMAT)


DateTimeField.register_lookup(ExactLookup)
DateTimeField.register_lookup(LteLookup)
DateTimeField.register_lookup(GteLookup)


EPOCH = timezone.utc.localize(datetime.datetime.utcfromtimestamp(0))


def datetime_from_timestamp(ts):
    return timezone.utc.localize(datetime.datetime.utcfromtimestamp(ts))


def timestamp_from_datetime(dt):
    return int((timezone.utc.normalize(dt) - EPOCH).total_seconds())


class TimestampField(LdapFieldMixin, fields.DateTimeField):
    """
    A field storing a datetime as a UNIX timestamp.

    See for instance nis.schema > shadowAccount > shadowLastChange.
    """

    def from_ldap(self, value, connection):
        if len(value) == 0:
            return None
        return datetime_from_timestamp(value[0].decode(connection.charset))

    def get_prep_value(self, value):
        return str(timestamp_from_datetime(value))


TimestampField.register_lookup(ExactLookup)
TimestampField.register_lookup(LteLookup)
TimestampField.register_lookup(GteLookup)
