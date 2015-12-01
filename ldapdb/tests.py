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
from django.db.models import Q
from django.db.models.sql import Query
from django.test import TestCase

from ldapdb import escape_ldap_filter
from ldapdb.models import Model, fields
from ldapdb.backends.ldap.compiler import where_as_ldap


class TestModel(Model):
    cn = fields.CharField()
    uid = fields.IntegerField()
    fuid = fields.FloatField()
    memberUid = fields.ListField()
    birthday = fields.DateField()
    givenName = fields.CharField()


class WhereTestCase(TestCase):
    def _make_where(self, *args, **kwargs):
        q = Query(TestModel)
        for arg in args:
            q.add_q(arg)
        q.add_q(Q(**kwargs))
        return q.where

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
        where = self._make_where(Q(cn__exact="test"))
        self.assertEqual(where_as_ldap(where), ("(cn=test)", []))

        where = self._make_where(Q(cn__exact="(test)"))
        self.assertEqual(where_as_ldap(where), ("(cn=\\28test\\29)", []))

    def test_char_field_in(self):
        where = self._make_where(Q(cn__in=['foo', 'bar']))
        self.assertEqual(where_as_ldap(where), ("(|(cn=foo)(cn=bar))", []))

        where = self._make_where(Q(cn__in=['(foo)', '(bar)']))
        self.assertEqual(where_as_ldap(where), ("(|(cn=\\28foo\\29)(cn=\\28bar\\29))", []))

    def test_char_field_startswith(self):
        where = self._make_where(Q(cn__startswith="test"))
        self.assertEqual(where_as_ldap(where), ("(cn=test*)", []))

        where = self._make_where(Q(cn__startswith="te*st"))
        self.assertEqual(where_as_ldap(where), ("(cn=te\\2ast*)", []))

    def test_char_field_endswith(self):
        where = self._make_where(Q(cn__endswith="test"))
        self.assertEqual(where_as_ldap(where), ("(cn=*test)", []))

        where = self._make_where(Q(cn__endswith="te*st"))
        self.assertEqual(where_as_ldap(where), ("(cn=*te\\2ast)", []))

    def test_char_field_contains(self):
        where = self._make_where(Q(cn__contains="test"))
        self.assertEqual(where_as_ldap(where), ("(cn=*test*)", []))

        where = self._make_where(Q(cn__contains="te*st"))
        self.assertEqual(where_as_ldap(where), ("(cn=*te\\2ast*)", []))

    def test_integer_field(self):
        where = self._make_where(Q(uid__exact=1))
        self.assertEqual(where_as_ldap(where), ("(uid=1)", []))

        where = self._make_where(Q(uid__gte=1))
        self.assertEqual(where_as_ldap(where), ("(uid>=1)", []))

        where = self._make_where(Q(uid__lte=1))
        self.assertEqual(where_as_ldap(where), ("(uid<=1)", []))

    def test_float_field(self):
        where = self._make_where(Q(fuid__exact=1.2))
        self.assertEqual(where_as_ldap(where), ("(fuid=1.2)", []))

        where = self._make_where(Q(fuid__gte=1.2))
        self.assertEqual(where_as_ldap(where), ("(fuid>=1.2)", []))

        where = self._make_where(Q(fuid__lte=1.2))
        self.assertEqual(where_as_ldap(where), ("(fuid<=1.2)", []))

    def test_list_field_contains(self):
        where = self._make_where(Q(memberUid__contains="foouser"))
        self.assertEqual(where_as_ldap(where), ("(memberUid=foouser)", []))

        where = self._make_where(Q(memberUid__contains="(foouser)"))
        self.assertEqual(where_as_ldap(where), ("(memberUid=\\28foouser\\29)", []))

    def test_date_field(self):
        where = self._make_where(Q(birthday__exact="2013-09-03"))
        self.assertEqual(where_as_ldap(where), ("(birthday=2013-09-03)", []))

    def test_and(self):
        q1 = Q(cn__exact="foo")
        q2 = Q(givenName__exact="bar")
        where = self._make_where(q1 & q2)
        self.assertEqual(where_as_ldap(where), ("(&(cn=foo)(givenName=bar))", []))

    def test_or(self):
        q1 = Q(cn__exact="foo")
        q2 = Q(givenName__exact="bar")
        where = self._make_where(q1 | q2)
        self.assertEqual(where_as_ldap(where), ("(|(cn=foo)(givenName=bar))", []))
