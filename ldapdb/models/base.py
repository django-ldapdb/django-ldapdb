# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import logging

import django.db.models
import ldap
from django.db import connections, router
from django.db.models import signals

from . import fields as ldapdb_fields

logger = logging.getLogger('ldapdb')


class Model(django.db.models.base.Model):
    """
    Base class for all LDAP models.
    """
    dn = ldapdb_fields.CharField(max_length=200, primary_key=True)

    # meta-data
    base_dn = None
    search_scope = ldap.SCOPE_SUBTREE
    object_classes = ['top']

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self._saved_dn = self.dn

    def build_rdn(self):
        """
        Build the Relative Distinguished Name for this entry.
        """
        bits = []
        for field in self._meta.fields:
            if field.db_column and field.primary_key:
                bits.append("%s=%s" % (field.db_column,
                                       getattr(self, field.name)))
        if not len(bits):
            raise Exception("Could not build Distinguished Name")
        return '+'.join(bits)

    def build_dn(self):
        """
        Build the Distinguished Name for this entry.
        """
        return "%s,%s" % (self.build_rdn(), self.base_dn)

    def delete(self, using=None):
        """
        Delete this entry.
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        logger.debug("Deleting LDAP entry %s" % self.dn)
        connection.delete_s(self.dn)
        signals.post_delete.send(sender=self.__class__, instance=self)

    def _save_table(self, raw=False, cls=None, force_insert=None, force_update=None, using=None, update_fields=None):
        """
        Saves the current instance.
        """
        # Connection aliasing
        connection = connections[using]

        create = bool(force_insert or not self.dn)

        # Prepare fields
        if update_fields:
            target_fields = [
                self._meta.get_field(name)
                for name in update_fields
            ]
        else:
            target_fields = [
                field
                for field in cls._meta.get_fields(include_hidden=True)
                if field.concrete and not field.primary_key
            ]

        def get_field_value(field, instance):
            python_value = getattr(instance, field.attname)
            return field.get_db_prep_save(python_value, connection=connection)

        if create:
            old = None
        else:
            old = cls.objects.using(using).get(dn=self._saved_dn)
        changes = {
            field.db_column: (
                None if old is None else get_field_value(field, old),
                get_field_value(field, self),
            )
            for field in target_fields
        }

        # Actual saving

        old_dn = self.dn
        new_dn = self.build_dn()
        updated = False

        # Insertion
        if create:
            # FIXME(rbarrois): This should be handled through a hidden field.
            hidden_values = [
                ('objectClass', [obj_class.encode('utf-8') for obj_class in self.object_classes])
            ]
            new_values = hidden_values + [
                (colname, change[1])
                for colname, change in sorted(changes.items())
                if change[1] != []
            ]
            new_dn = self.build_dn()
            logger.debug("Creating new LDAP entry %s", new_dn)
            connection.add_s(new_dn, new_values)

        # Update
        else:
            modlist = []
            for colname, change in sorted(changes.items()):
                old_value, new_value = change
                if old_value == new_value:
                    continue
                modlist.append((
                    ldap.MOD_DELETE if new_value == [] else ldap.MOD_REPLACE,
                    colname,
                    new_value,
                ))

            if new_dn != old_dn:
                logger.debug("renaming ldap entry %s to %s", old_dn, new_dn)
                connection.rename_s(old_dn, self.build_rdn())

            if modlist:
                logger.debug("Modifying existing LDAP entry %s", new_dn)
                connection.modify_s(new_dn, modlist)
            updated = True

        self.dn = new_dn

        # Finishing
        self._saved_dn = self.dn
        return updated

    @classmethod
    def scoped(base_class, base_dn):
        """
        Returns a copy of the current class with a different base_dn.
        """
        class Meta:
            proxy = True
            verbose_name = base_class._meta.verbose_name
            verbose_name_plural = base_class._meta.verbose_name_plural
        import re
        suffix = re.sub('[=,]', '_', base_dn)
        name = "%s_%s" % (base_class.__name__, str(suffix))
        new_class = type(str(name), (base_class,), {
            'base_dn': base_dn, '__module__': base_class.__module__,
            'Meta': Meta})
        return new_class

    class Meta:
        abstract = True
