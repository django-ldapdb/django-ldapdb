# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import collections
import ldap
import re
import sys

import django
from django.db.models.sql import compiler
from django.db.models.sql.where import AND, OR, WhereNode

from ldapdb.models.fields import ListField

if django.VERSION >= (1, 8):
    from django.db.models import aggregates
else:
    from django.db.models.sql import aggregates

if sys.version_info[0] < 3:
    integer_types = (int, long)
else:
    integer_types = (int,)


_ORDER_BY_LIMIT_OFFSET_RE = re.compile(
    r'(?:\bORDER BY\b\s+(.+?))?\s*(?:\bLIMIT\b\s+(-?\d+))?\s*(?:\bOFFSET\b\s+(\d+))?$')


class LdapDBError(Exception):
    """Base class for LDAPDB errors."""


LdapLookup = collections.namedtuple('LdapLookup', ['base', 'scope', 'filterstr'])


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

    if (len(query.where.children) == 1
            and not isinstance(query.where.children[0], WhereNode)
            and query.where.children[0].lhs.target.column == 'dn'):

        lookup = query.where.children[0]
        if lookup.lookup_name != 'exact':
            raise LdapDBError("Unsupported dn lookup: %s" % lookup.lookup_name)

        return LdapLookup(
            base=lookup.rhs,
            scope=ldap.SCOPE_BASE,
            filterstr='(&%s)' % filterstr,
        )

    sql = where_as_ldap(query.where)
    filterstr += sql
    return LdapLookup(
        base=query.model.base_dn,
        scope=query.model.search_scope,
        filterstr='(&%s)' % filterstr,
    )


def where_as_ldap(where):
    bits = []
    for item in where.children:
        if isinstance(item, WhereNode):
            # A sub-node: using Q objects for complex lookups.
            sql = where_as_ldap(item)
            bits.append(sql)
            continue

        attr_name = item.lhs.target.column
        comp = get_lookup_operator(item.lookup_name)
        values = item.rhs

        if attr_name == 'dn':
            raise LdapDBError("Looking up more than one distinguishedName is unsupported.")

        if item.lookup_name == 'in':
            equal_bits = ["(%s%s%s)" % (attr_name, comp, value) for value in values]
            clause = '(|%s)' % ''.join(equal_bits)
        else:
            clause = "(%s%s%s)" % (attr_name, comp, values)

        bits.append(clause)

    if not len(bits):
        return ''

    if len(bits) == 1:
        sql_string = bits[0]
    elif where.connector == AND:
        sql_string = '(&%s)' % ''.join(sorted(bits))
    elif where.connector == OR:
        sql_string = '(|%s)' % ''.join(sorted(bits))
    else:
        raise LdapDBError("Unhandled WHERE connector: %s" % where.connector)

    if where.negated:
        sql_string = ('(!%s)' % sql_string)

    return sql_string


class SQLCompiler(compiler.SQLCompiler):

    def execute_sql(self, result_type=compiler.SINGLE):
        if result_type != compiler.SINGLE:
            raise Exception("LDAP does not support MULTI queries")

        lookup = query_as_ldap(self.query)

        if lookup is None:
            return

        try:
            vals = self.connection.search_s(
                base=lookup.base,
                scope=lookup.scope,
                filterstr=lookup.filterstr,
                attrlist=['dn'],
            )
        except ldap.NO_SUCH_OBJECT:
            vals = []

        if not vals:
            return None

        output = []
        if django.VERSION >= (1, 8):
            self.setup_query()
            for e in self.select:
                if isinstance(e[0], aggregates.Count):
                    # Check if the SQL query has a limit value and append
                    # that value, else append the length of the return values
                    # from LDAP.
                    sql = self.as_sql()[0]
                    if hasattr(self.query, 'subquery'):
                        sql = self.query.subquery
                    m = _ORDER_BY_LIMIT_OFFSET_RE.search(sql)
                    limit = m.group(2)
                    offset = m.group(3)
                    if limit and int(limit) >= 0:
                        output.append(int(limit))
                    elif offset:
                        output.append(len(vals) - int(offset))
                    else:
                        output.append(len(vals))
                else:
                    output.append(e[0])
        else:
            for alias, col in self.query.extra_select.items():
                output.append(col[0])
            for key, aggregate in self.query.aggregate_select.items():
                if isinstance(aggregate, aggregates.Count):
                    output.append(len(vals))
                else:
                    output.append(None)
        return output

    def results_iter(self, results=None):
        lookup = query_as_ldap(self.query)
        if lookup is None:
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
                base=lookup.base,
                scope=lookup.scope,
                filterstr=lookup.filterstr,
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

        for fieldname in reversed(ordering):
            if fieldname.startswith('-'):
                sort_field = fieldname[1:]
                reverse = True
            else:
                sort_field = fieldname
                reverse = False

            if sort_field == 'pk':
                sort_field = self.query.model._meta.pk.name
            field = self.query.model._meta.get_field(sort_field)

            def get_key(obj):
                attr = field.from_ldap(
                    obj[1].get(field.db_column, []),
                    connection=self.connection,
                )
                if hasattr(attr, 'lower'):
                    attr = attr.lower()
                return attr
            vals = sorted(vals, key=get_key, reverse=reverse)

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
            if django.VERSION >= (1, 8):
                self.setup_query()
                for e in self.select:
                    if isinstance(e[0], aggregates.Count):
                        value = 0
                        input_field = e[0].get_source_expressions()[0].field
                        if input_field.attname == 'dn':
                            value = 1
                        elif hasattr(input_field, 'from_ldap'):
                            result = input_field.from_ldap(
                                attrs.get(input_field.db_column, []),
                                connection=self.connection)
                            if result:
                                value = 1
                                if isinstance(input_field, ListField):
                                    value = len(result)
                        row.append(value)
                    else:
                        if e[0].field.attname == 'dn':
                            row.append(dn)
                        elif hasattr(e[0].field, 'from_ldap'):
                            row.append(e[0].field.from_ldap(
                                attrs.get(e[0].field.db_column, []),
                                connection=self.connection))
                        else:
                            row.append(None)
            else:
                for field in iter(fields):
                    if field.attname == 'dn':
                        row.append(dn)
                    elif hasattr(field, 'from_ldap'):
                        row.append(field.from_ldap(
                            attrs.get(field.db_column, []),
                            connection=self.connection,
                        ))
                    else:
                        row.append(None)
                for key, aggregate in self.query.aggregate_select.items():
                    if isinstance(aggregate, aggregates.Count):
                        value = 0
                        if aggregate.source.attname == 'dn':
                            value = 1
                        elif hasattr(aggregate.source, 'from_ldap'):
                            result = aggregate.source.from_ldap(
                                attrs.get(aggregate.source.db_column, []),
                                connection=self.connection)
                            if result:
                                value = 1
                                if isinstance(aggregate.source, ListField):
                                    value = len(result)
                        row.append(value)
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
                iterator.next()
                return True
            except:
                return False
        else:
            return False


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    def execute_sql(self, result_type=compiler.MULTI):
        lookup = query_as_ldap(self.query)
        if not lookup:
            return

        try:
            vals = self.connection.search_s(
                base=lookup.base,
                scope=lookup.scope,
                filterstr=lookup.filterstr,
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
    def execute_sql(self, result_type=compiler.SINGLE):
        # Return only number values through the aggregate compiler
        output = super(SQLAggregateCompiler, self).execute_sql(result_type)
        if sys.version_info < (3,):
            return filter(lambda a: isinstance(a, int), output)
        return filter(lambda a: isinstance(a, integer_types), output)


if django.VERSION < (1, 8):
    class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
        pass
