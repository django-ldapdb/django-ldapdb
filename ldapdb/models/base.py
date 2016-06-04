# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import ldap
import logging

import django.db.models
from django.db import connections, router
from django.db.models import signals

import ldapdb  # noqa


logger = logging.getLogger('ldapdb')


class Model(django.db.models.base.Model):
    """
    Base class for all LDAP models.
    """
    dn = django.db.models.fields.CharField(max_length=200)

    # meta-data
    base_dn = None
    search_scope = ldap.SCOPE_SUBTREE
    object_classes = ['top']

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self.saved_pk = self.pk

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
        raise Exception("Could not build Distinguished Name")

    def delete(self, using=None):
        """
        Delete this entry.
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        logger.debug("Deleting LDAP entry %s" % self.dn)
        connection.delete_s(self.dn)
        signals.post_delete.send(sender=self.__class__, instance=self)

    def save(self, using=None):
        """
        Saves the current instance.
        """
        signals.pre_save.send(sender=self.__class__, instance=self)

        using = using or router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        if not self.dn:
            # create a new entry
            record_exists = False
            entry = [
                ('objectClass', [obj_class.encode('utf-8') for obj_class in self.object_classes])
            ]
            new_dn = self.build_dn()

            for field in self._meta.fields:
                if not field.db_column:
                    continue
                value = getattr(self, field.name)
                value = field.get_db_prep_save(value, connection=connection)
                if value:
                    entry.append((field.db_column, value))

            logger.debug("Creating new LDAP entry %s" % new_dn)
            connection.add_s(new_dn, entry)

            # update object
            self.dn = new_dn

        else:
            # update an existing entry
            record_exists = True
            modlist = []
            orig = self.__class__.objects.using(using).get(pk=self.saved_pk)
            for field in self._meta.fields:
                if not field.db_column:
                    continue
                old_value = getattr(orig, field.name, None)
                new_value = getattr(self, field.name, None)
                if old_value != new_value:
                    new_value = field.get_db_prep_save(new_value, connection=connection)
                    if new_value:
                        modlist.append((ldap.MOD_REPLACE, field.db_column, new_value))
                    elif old_value:
                        modlist.append((ldap.MOD_DELETE, field.db_column, None))

            if len(modlist):
                # handle renaming
                new_dn = self.build_dn()
                if new_dn != self.dn:
                    logger.debug("Renaming LDAP entry %s to %s" % (self.dn,
                                                                   new_dn))
                    connection.rename_s(self.dn, self.build_rdn())
                    self.dn = new_dn

                logger.debug("Modifying existing LDAP entry %s" % self.dn)
                connection.modify_s(self.dn, modlist)
            else:
                logger.debug("No changes to be saved to LDAP entry %s" %
                             self.dn)

        # done
        self.saved_pk = self.pk
        signals.post_save.send(sender=self.__class__, instance=self,
                               created=(not record_exists))

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
