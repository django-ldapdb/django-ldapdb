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

import ldap

from django.db.models.sql import aggregates, compiler
from django.db.models.sql.where import AND, OR


def get_lookup_operator(lookup_type):
    if lookup_type == 'gte':
        return '>='
    elif lookup_type == 'lte':
        return '<='
    else:
        return '='


def query_as_ldap(query):
    # starting with django 1.6 we can receive empty querysets
    if hasattr(query, 'is_empty') and query.is_empty():
        return

    filterstr = ''.join(['(objectClass=%s)' % cls for cls in
                         query.model.object_classes])
    sql, params = where_as_ldap(query.where)
    filterstr += sql
    return '(&%s)' % filterstr


def where_as_ldap(self):
    bits = []
    for item in self.children:
        if hasattr(item, 'lhs') and hasattr(item, 'rhs'):
            # Django 1.7
            item = item.lhs.target.column, item.lookup_name, None, item.rhs
        elif hasattr(item, 'as_sql'):
            sql, params = where_as_ldap(item)
            bits.append(sql)
            continue

        constraint, lookup_type, y, values = item
        if hasattr(constraint, 'col'):
            constraint = constraint.col
        comp = get_lookup_operator(lookup_type)
        if lookup_type == 'in':
            equal_bits = ["(%s%s%s)" % (constraint, comp, value) for value
                          in values]
            clause = '(|%s)' % ''.join(equal_bits)
        else:
            clause = "(%s%s%s)" % (constraint, comp, values)

        bits.append(clause)

    if not len(bits):
        return '', []

    if len(bits) == 1:
        sql_string = bits[0]
    elif self.connector == AND:
        sql_string = '(&%s)' % ''.join(bits)
    elif self.connector == OR:
        sql_string = '(|%s)' % ''.join(bits)
    else:
        raise Exception("Unhandled WHERE connector: %s" % self.connector)

    if self.negated:
        sql_string = ('(!%s)' % sql_string)

    return sql_string, []


class SQLCompiler(object):
    def __init__(self, query, connection, using):
        self.query = query
        self.connection = connection
        self.using = using

    def execute_sql(self, result_type=compiler.MULTI):
        if result_type != compiler.SINGLE:
            raise Exception("LDAP does not support MULTI queries")

        for key, aggregate in self.query.aggregate_select.items():
            if not isinstance(aggregate, aggregates.Count):
                raise Exception("Unsupported aggregate %s" % aggregate)

        filterstr = query_as_ldap(self.query)
        if not filterstr:
            return

        try:
            vals = self.connection.search_s(
                self.query.model.base_dn,
                self.query.model.search_scope,
                filterstr=filterstr,
                attrlist=['dn'],
            )
        except ldap.NO_SUCH_OBJECT:
            vals = []

        if not vals:
            return None

        output = []
        for alias, col in self.query.extra_select.iteritems():
            output.append(col[0])
        for key, aggregate in self.query.aggregate_select.items():
            if isinstance(aggregate, aggregates.Count):
                output.append(len(vals))
            else:
                output.append(None)
        return output

    def results_iter(self):
        filterstr = query_as_ldap(self.query)
        if not filterstr:
            return

        if hasattr(self.query, 'select_fields') and len(self.query.select_fields):
            # django < 1.6
            fields = self.query.select_fields
        elif len(self.query.select):
            # django >= 1.6
            fields = [x.field for x in self.query.select]
        else:
            fields = self.query.model._meta.fields

        attrlist = [x.db_column for x in fields if x.db_column]

        try:
            vals = self.connection.search_s(
                self.query.model.base_dn,
                self.query.model.search_scope,
                filterstr=filterstr,
                attrlist=attrlist,
            )
        except ldap.NO_SUCH_OBJECT:
            return

        # perform sorting
        if self.query.extra_order_by:
            ordering = self.query.extra_order_by
        elif not self.query.default_ordering:
            ordering = self.query.order_by
        else:
            ordering = self.query.order_by or self.query.model._meta.ordering

        def cmpvals(x, y):
            for fieldname in ordering:
                if fieldname.startswith('-'):
                    fieldname = fieldname[1:]
                    negate = True
                else:
                    negate = False
                if fieldname == 'pk':
                    fieldname = self.query.model._meta.pk.name
                field = self.query.model._meta.get_field(fieldname)
                attr_x = field.from_ldap(x[1].get(field.db_column, []),
                                         connection=self.connection)
                attr_y = field.from_ldap(y[1].get(field.db_column, []),
                                         connection=self.connection)
                # perform case insensitive comparison
                if hasattr(attr_x, 'lower'):
                    attr_x = attr_x.lower()
                if hasattr(attr_y, 'lower'):
                    attr_y = attr_y.lower()
                val = negate and cmp(attr_y, attr_x) or cmp(attr_x, attr_y)
                if val:
                    return val
            return 0
        vals = sorted(vals, cmp=cmpvals)

        # process results
        pos = 0
        results = []
        for dn, attrs in vals:
            # FIXME : This is not optimal, we retrieve more results than we
            # need but there is probably no other options as we can't perform
            # ordering server side.
            if (self.query.low_mark and pos < self.query.low_mark) or \
               (self.query.high_mark is not None and
                    pos >= self.query.high_mark):
                pos += 1
                continue
            row = []
            for field in iter(fields):
                if field.attname == 'dn':
                    row.append(dn)
                elif hasattr(field, 'from_ldap'):
                    row.append(field.from_ldap(attrs.get(field.db_column, []),
                                               connection=self.connection))
                else:
                    row.append(None)
            if self.query.distinct:
                if row in results:
                    continue
                else:
                    results.append(row)
            yield row
            pos += 1

    def has_results(self):
        import inspect
        iterator = self.results_iter()
        if inspect.isgenerator(iterator):
            try:
                obj = iterator.next()
                return True
            except:
                return False
        else:
            return False

class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    def execute_sql(self, result_type=compiler.MULTI):
        filterstr = query_as_ldap(self.query)
        if not filterstr:
            return

        try:
            vals = self.connection.search_s(
                self.query.model.base_dn,
                self.query.model.search_scope,
                filterstr=filterstr,
                attrlist=['dn'],
            )
        except ldap.NO_SUCH_OBJECT:
            return

        # FIXME : there is probably a more efficient way to do this
        for dn, attrs in vals:
            self.connection.delete_s(dn)


class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass


class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass


class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
    pass
