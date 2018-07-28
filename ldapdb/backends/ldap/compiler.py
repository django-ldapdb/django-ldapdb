# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import collections
import re
import sys

import ldap
from django.db.models import aggregates
from django.db.models.sql import compiler
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.db.models.sql.where import AND, OR, WhereNode

from ldapdb import escape_ldap_filter
from ldapdb.models.fields import ListField

if sys.version_info[0] < 3:
    integer_types = (int, long)  # noqa: F821
else:
    integer_types = (int,)


_ORDER_BY_LIMIT_OFFSET_RE = re.compile(
    r'(?:\bORDER BY\b\s+(.+?))?\s*(?:\bLIMIT\b\s+(-?\d+))?\s*(?:\bOFFSET\b\s+(\d+))?$')


class LdapDBError(Exception):
    """Base class for LDAPDB errors."""


LdapLookup = collections.namedtuple('LdapLookup', ['base', 'scope', 'filterstr'])


def query_as_ldap(query, compiler, connection):
    """Convert a django.db.models.sql.query.Query to a LdapLookup."""
    if query.is_empty():
        return

    if query.model._meta.model_name == 'migration' and not hasattr(query.model, 'object_classes'):
        # FIXME(rbarrois): Support migrations
        return

    # FIXME(rbarrois): this could be an extra Where clause
    filterstr = ''.join(['(objectClass=%s)' % cls for cls in
                         query.model.object_classes])

    # FIXME(rbarrois): Remove this code as part of #101
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

    sql, params = compiler.compile(query.where)
    if sql:
        filterstr += '(%s)' % (sql % tuple(escape_ldap_filter(param) for param in params))
    return LdapLookup(
        base=query.model.base_dn,
        scope=query.model.search_scope,
        filterstr='(&%s)' % filterstr,
    )


def where_node_as_ldap(where, compiler, connection):
    """Parse a django.db.models.sql.where.WhereNode.

    Returns:
        (clause, [params]): the filter clause, with a list of unescaped parameters.
    """
    bits, params = [], []
    for item in where.children:
        if isinstance(item, WhereNode):
            clause, clause_params = compiler.compile(item)
        else:
            clause, clause_params = item.as_sql(compiler, connection)

        bits.append(clause)
        params.extend(clause_params)

    if not bits:
        return '', []

    # FIXME(rbarrois): shouldn't we flatten recursive AND / OR?
    if len(bits) == 1:
        clause = bits[0]
    elif where.connector == AND:
        clause = '&' + ''.join('(%s)' % bit for bit in bits)
    elif where.connector == OR:
        clause = '|' + ''.join('(%s)' % bit for bit in bits)
    else:
        raise LdapDBError("Unhandled WHERE connector: %s" % where.connector)

    if where.negated:
        clause = ('!(%s)' % clause)

    return clause, params


class SQLCompiler(compiler.SQLCompiler):
    """LDAP-based SQL compiler."""

    def compile(self, node, *args, **kwargs):
        """Parse a WhereNode to a LDAP filter string."""
        if isinstance(node, WhereNode):
            return where_node_as_ldap(node, self, self.connection)
        return super(SQLCompiler, self).compile(node, *args, **kwargs)

    def execute_sql(self, result_type=compiler.SINGLE, chunked_fetch=False,
                    chunk_size=GET_ITERATOR_CHUNK_SIZE):
        if result_type != compiler.SINGLE:
            raise Exception("LDAP does not support MULTI queries")

        # Setup self.select, self.klass_info, self.annotation_col_map
        # All expected from ModelIterable.__iter__
        self.pre_sql_setup()
        lookup = query_as_ldap(self.query, compiler=self, connection=self.connection)

        if lookup is None:
            return

        try:
            vals = self.connection.search_s(
                base=lookup.base,
                scope=lookup.scope,
                filterstr=lookup.filterstr,
                attrlist=['dn'],
            )
            # Flatten iterator
            vals = list(vals)
        except ldap.NO_SUCH_OBJECT:
            vals = []

        if not vals:
            return None

        output = []
        self.setup_query()
        for e in self.select:
            if isinstance(e[0], aggregates.Count):
                # Check if the SQL query has a limit value and append
                # that value, else append the length of the return values
                # from LDAP.
                sql = self.as_sql()[0]
                if hasattr(self.query, 'subquery') and self.query.subquery:
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
        return output

    def results_iter(self, results=None, tuple_expected=False, chunked_fetch=False, chunk_size=GET_ITERATOR_CHUNK_SIZE):
        lookup = query_as_ldap(self.query, compiler=self, connection=self.connection)
        if lookup is None:
            return

        if len(self.query.select):
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

            if sort_field == 'dn':
                vals = sorted(vals, key=lambda pair: pair[0], reverse=reverse)
            else:
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
                next(iterator)
                return True
            except StopIteration:
                return False
        else:
            return False


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    def execute_sql(self, result_type=compiler.MULTI):
        lookup = query_as_ldap(self.query, compiler=self, connection=self.connection)
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
