# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project


import datetime

from django.db import connections
from django.db.models import expressions
from django.db.models.sql import query as django_query
from django.db.models.sql.where import AND, OR, WhereNode
from django.test import TestCase
from django.utils import timezone

from ldapdb import escape_ldap_filter, models
from ldapdb.backends.ldap import compiler as ldapdb_compiler
from ldapdb.models import fields

UTC = timezone.utc
UTC_PLUS_ONE = timezone.get_fixed_timezone(60)
UTC_MINUS_2_HALF = timezone.get_fixed_timezone(-150)


class FakeModel(models.Model):
    class Meta:
        abstract = True

    base_dn = 'ou=test,dc=example,dc=org'
    object_classes = ['inetOrgPerson']
    name = fields.CharField(db_column='cn')


class DateTimeTests(TestCase):
    CONVERSIONS = {
        '': None,
        '20180102030405.067874Z': datetime.datetime(2018, 1, 2, 3, 4, 5, 67874, tzinfo=UTC),
        # Sub-microsecond is ignored by Python
        '20180102030405.067874846Z': datetime.datetime(2018, 1, 2, 3, 4, 5, 67874, tzinfo=UTC),
        # Sub-hour precision is optional
        '2018010203Z': datetime.datetime(2018, 1, 2, 3, tzinfo=UTC),
        # Support UTC offsets
        '201801020304+0100': datetime.datetime(2018, 1, 2, 3, 4, tzinfo=UTC_PLUS_ONE),
        # Minutes are optional for UTC offsets
        '201801020304+01': datetime.datetime(2018, 1, 2, 3, 4, tzinfo=UTC_PLUS_ONE),
        # Check negative offsets
        '201801020304-0230': datetime.datetime(2018, 1, 2, 3, 4, tzinfo=UTC_MINUS_2_HALF),
    }

    def test_conversions(self):
        for raw, expected in sorted(self.CONVERSIONS.items()):
            converted = fields.datetime_from_ldap(raw)
            self.assertEqual(
                expected,
                converted,
                "Mismatch for %r: expected=%r, got=%r" % (raw, expected, converted),
            )


class TimestampTests(TestCase):
    CONVERSIONS = {
        0: datetime.datetime(1970, 1, 1, tzinfo=UTC),
        1530139989: datetime.datetime(2018, 6, 27, 22, 53, 9, tzinfo=UTC),
    }

    def test_conversions(self):
        for raw, expected in sorted(self.CONVERSIONS.items()):
            converted = fields.datetime_from_timestamp(raw)
            self.assertEqual(
                expected,
                converted,
                "Mismatch for %r: expected=%r, got=%r" % (raw, expected, converted),
            )
            retro_converted = fields.timestamp_from_datetime(converted)
            self.assertEqual(
                raw,
                retro_converted,
                "Mismatch for %r: expected=%r, got=%r" % (raw, raw, retro_converted),
            )


class WhereTestCase(TestCase):
    def _build_lookup(self, field_name, lookup, value, field=fields.CharField):
        fake_field = field()
        fake_field.set_attributes_from_name(field_name)
        lhs = expressions.Col('faketable', fake_field, fake_field)
        lookup = lhs.get_lookup(lookup)
        return lookup(lhs, value)

    def _where_as_ldap(self, where):
        query = django_query.Query(model=FakeModel)
        compiler = ldapdb_compiler.SQLCompiler(
            query=query,
            connection=connections['ldap'],
            using=None,
        )
        pattern, params = compiler.compile(where)
        return '(%s)' % (pattern % tuple(escape_ldap_filter(param) for param in params))

    def test_escape(self):
        self.assertEqual(escape_ldap_filter(u'fôöbàr'), u'fôöbàr')
        self.assertEqual(escape_ldap_filter('foo*bar'), 'foo\\2abar')
        self.assertEqual(escape_ldap_filter('foo(bar'), 'foo\\28bar')
        self.assertEqual(escape_ldap_filter('foo)bar'), 'foo\\29bar')
        self.assertEqual(escape_ldap_filter('foo\\bar'), 'foo\\5cbar')
        self.assertEqual(escape_ldap_filter('foo\\bar*wiz'), 'foo\\5cbar\\2awiz')

    def test_char_field_max_length(self):
        self.assertEqual(fields.CharField(max_length=42).max_length, 42)

    def test_char_field_exact(self):
        where = WhereNode()
        where.add(self._build_lookup('cn', 'exact', "test"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=test)")

        where = WhereNode()
        where.add(self._build_lookup('cn', 'exact', "(test)"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=\\28test\\29)")

    def test_char_field_in(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'in', ["foo", "bar"]), AND)
        self.assertEqual(self._where_as_ldap(where), "(|(cn=foo)(cn=bar))")

        where = WhereNode()
        where.add(self._build_lookup("cn", 'in', ["(foo)", "(bar)"]), AND)
        self.assertEqual(self._where_as_ldap(where), "(|(cn=\\28foo\\29)(cn=\\28bar\\29))")

    def test_char_field_startswith(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'startswith', "test"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=test*)")

        where = WhereNode()
        where.add(self._build_lookup("cn", 'startswith', "te*st"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=te\\2ast*)")

    def test_char_field_endswith(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'endswith', "test"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=*test)")

        where = WhereNode()
        where.add(self._build_lookup("cn", 'endswith', "te*st"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=*te\\2ast)")

    def test_char_field_contains(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'contains', "test"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=*test*)")

        where = WhereNode()
        where.add(self._build_lookup("cn", 'contains', "te*st"), AND)
        self.assertEqual(self._where_as_ldap(where), "(cn=*te\\2ast*)")

    def test_integer_field(self):
        where = WhereNode()
        where.add(self._build_lookup("uid", 'exact', 1, field=fields.IntegerField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid=1)")

        where = WhereNode()
        where.add(self._build_lookup("uid", 'gte', 1, field=fields.IntegerField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid>=1)")

        where = WhereNode()
        where.add(self._build_lookup("uid", 'lte', 1, field=fields.IntegerField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid<=1)")

        where = WhereNode()
        where.add(self._build_lookup("uid", 'in', [1, 2], field=fields.IntegerField), AND)
        self.assertEqual(self._where_as_ldap(where), "(|(uid=1)(uid=2))")

    def test_float_field(self):
        where = WhereNode()
        where.add(self._build_lookup("uid", 'exact', 1.2, field=fields.FloatField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid=1.2)")

        where = WhereNode()
        where.add(self._build_lookup("uid", 'gte', 1.2, field=fields.FloatField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid>=1.2)")

        where = WhereNode()
        where.add(self._build_lookup("uid", 'lte', 1.2, field=fields.FloatField), AND)
        self.assertEqual(self._where_as_ldap(where), "(uid<=1.2)")

    def test_boolean_field(self):
        where = WhereNode()
        where.add(self._build_lookup("isSuperuser", 'exact', True, field=fields.BooleanField), AND)
        self.assertEqual(self._where_as_ldap(where), "(isSuperuser=TRUE)")

        where = WhereNode()
        where.add(self._build_lookup("isSuperuser", 'exact', False, field=fields.BooleanField), AND)
        self.assertEqual(self._where_as_ldap(where), "(isSuperuser=FALSE)")

        where = WhereNode()
        where.add(self._build_lookup("isSuperuser", 'exact', 1, field=fields.BooleanField), AND)
        self.assertEqual(self._where_as_ldap(where), "(isSuperuser=TRUE)")

        where = WhereNode()
        where.add(self._build_lookup("isSuperuser", 'exact', 0, field=fields.BooleanField), AND)
        self.assertEqual(self._where_as_ldap(where), "(isSuperuser=FALSE)")

    def test_list_field_contains(self):
        where = WhereNode()
        where.add(self._build_lookup("memberUid", 'contains', 'foouser', field=fields.ListField), AND)
        self.assertEqual(self._where_as_ldap(where), "(memberUid=foouser)")

        where = WhereNode()
        where.add(self._build_lookup("memberUid", 'contains', '(foouser)', field=fields.ListField), AND)
        self.assertEqual(self._where_as_ldap(where), "(memberUid=\\28foouser\\29)")

    def test_date_field(self):
        where = WhereNode()
        where.add(self._build_lookup("birthday", 'exact', '2013-09-03', field=fields.DateField), AND)
        self.assertEqual(self._where_as_ldap(where), "(birthday=2013-09-03)")

    def test_datetime_field(self):
        dt = datetime.datetime(2018, 6, 25, 20, 21, 22, tzinfo=UTC)

        where = WhereNode()
        where.add(self._build_lookup("modifyTimestamp", 'exact', dt, field=fields.DateTimeField,), AND)
        self.assertEqual(self._where_as_ldap(where), "(modifyTimestamp=20180625202122.000000Z)")

        where = WhereNode()
        where.add(self._build_lookup("modifyTimestamp", 'lte', dt, field=fields.DateTimeField,), AND)
        self.assertEqual(self._where_as_ldap(where), "(modifyTimestamp<=20180625202122.000000Z)")

        where = WhereNode()
        where.add(self._build_lookup("modifyTimestamp", 'gte', dt, field=fields.DateTimeField,), AND)
        self.assertEqual(self._where_as_ldap(where), "(modifyTimestamp>=20180625202122.000000Z)")

    def test_timestamp_field(self):
        dt = datetime.datetime(2018, 6, 25, 20, 21, 22, tzinfo=UTC)
        where = WhereNode()
        where.add(self._build_lookup("shadowLastChange", 'exact', dt, field=fields.TimestampField), AND)
        self.assertEqual(self._where_as_ldap(where), "(shadowLastChange=1529958082)")

    def test_and(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'exact', "foo", field=fields.CharField), AND)
        where.add(self._build_lookup("givenName", 'exact', "bar", field=fields.CharField), AND)
        self.assertEqual(self._where_as_ldap(where), "(&(cn=foo)(givenName=bar))")

    def test_or(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'exact', "foo", field=fields.CharField), AND)
        where.add(self._build_lookup("givenName", 'exact', "bar", field=fields.CharField), OR)
        self.assertEqual(self._where_as_ldap(where), "(|(cn=foo)(givenName=bar))")
