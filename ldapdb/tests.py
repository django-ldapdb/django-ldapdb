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

import django
from django.test import TestCase
from django.db.models.sql.where import AND, OR, WhereNode
from django.db.models.sql import datastructures
from django.db.models import expressions

from ldapdb import escape_ldap_filter
from ldapdb.backends.ldap.compiler import where_as_ldap
from ldapdb.models.fields import (CharField, IntegerField, FloatField,
                                  ListField, DateField)


class WhereTestCase(TestCase):
    def _build_lookup(self, field_name, lookup, value, field=CharField):
        fake_field = field()
        fake_field.set_attributes_from_name(field_name)
        if django.VERSION[:2] <= (1, 7):
            lhs = datastructures.Col('faketable', fake_field, fake_field)
        else:
            lhs = expressions.Col('faketable', fake_field, fake_field)
        lookup = lhs.get_lookup(lookup)
        return lookup(lhs, value)

    def test_escape(self):
        self.assertEqual(escape_ldap_filter(u'fôöbàr'), u'fôöbàr')
        self.assertEqual(escape_ldap_filter('foo*bar'), 'foo\\2abar')
        self.assertEqual(escape_ldap_filter('foo(bar'), 'foo\\28bar')
        self.assertEqual(escape_ldap_filter('foo)bar'), 'foo\\29bar')
        self.assertEqual(escape_ldap_filter('foo\\bar'), 'foo\\5cbar')
        self.assertEqual(escape_ldap_filter('foo\\bar*wiz'), 'foo\\5cbar\\2awiz')

    def test_char_field_max_length(self):
        self.assertEqual(CharField(max_length=42).max_length, 42)

    def test_char_field_exact(self):
        where = WhereNode()
        where.add(self._build_lookup('cn', 'exact', "test"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=test)", []))

        where = WhereNode()
        where.add(self._build_lookup('cn', 'exact', "(test)"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=\\28test\\29)", []))

    def test_char_field_in(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'in', ["foo", "bar"]), AND)
        self.assertEqual(where_as_ldap(where), ("(|(cn=foo)(cn=bar))", []))

        where = WhereNode()
        where.add(self._build_lookup("cn", 'in', ["(foo)", "(bar)"]), AND)
        self.assertEqual(where_as_ldap(where), ("(|(cn=\\28foo\\29)(cn=\\28bar\\29))", []))

    def test_char_field_startswith(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'startswith', "test"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=test*)", []))

        where = WhereNode()
        where.add(self._build_lookup("cn", 'startswith', "te*st"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=te\\2ast*)", []))

    def test_char_field_endswith(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'endswith', "test"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=*test)", []))

        where = WhereNode()
        where.add(self._build_lookup("cn", 'endswith', "te*st"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=*te\\2ast)", []))

    def test_char_field_contains(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'contains', "test"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=*test*)", []))

        where = WhereNode()
        where.add(self._build_lookup("cn", 'contains', "te*st"), AND)
        self.assertEqual(where_as_ldap(where), ("(cn=*te\\2ast*)", []))

    def test_integer_field(self):
        where = WhereNode()
        where.add(self._build_lookup("uid", 'exact', 1, field=IntegerField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid=1)", []))

        where = WhereNode()
        where.add(self._build_lookup("uid", 'gte', 1, field=IntegerField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid>=1)", []))

        where = WhereNode()
        where.add(self._build_lookup("uid", 'lte', 1, field=IntegerField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid<=1)", []))

    def test_float_field(self):
        where = WhereNode()
        where.add(self._build_lookup("uid", 'exact', 1.2, field=FloatField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid=1.2)", []))

        where = WhereNode()
        where.add(self._build_lookup("uid", 'gte', 1.2, field=FloatField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid>=1.2)", []))

        where = WhereNode()
        where.add(self._build_lookup("uid", 'lte', 1.2, field=FloatField), AND)
        self.assertEqual(where_as_ldap(where), ("(uid<=1.2)", []))

    def test_list_field_contains(self):
        where = WhereNode()
        where.add(self._build_lookup("memberUid", 'contains', 'foouser', field=ListField), AND)
        self.assertEqual(where_as_ldap(where), ("(memberUid=foouser)", []))

        where = WhereNode()
        where.add(self._build_lookup("memberUid", 'contains', '(foouser)', field=ListField), AND)
        self.assertEqual(where_as_ldap(where), ("(memberUid=\\28foouser\\29)", []))

    def test_date_field(self):
        where = WhereNode()
        where.add(self._build_lookup("birthday", 'exact', '2013-09-03', field=DateField), AND)
        self.assertEqual(where_as_ldap(where), ("(birthday=2013-09-03)", []))

    def test_and(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'exact', "foo", field=CharField), AND)
        where.add(self._build_lookup("givenName", 'exact', "bar", field=CharField), AND)
        self.assertEqual(where_as_ldap(where), ("(&(cn=foo)(givenName=bar))", []))

    def test_or(self):
        where = WhereNode()
        where.add(self._build_lookup("cn", 'exact', "foo", field=CharField), AND)
        where.add(self._build_lookup("givenName", 'exact', "bar", field=CharField), OR)
        self.assertEqual(where_as_ldap(where), ("(|(cn=foo)(givenName=bar))", []))
