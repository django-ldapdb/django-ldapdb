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

import copy
from functools import partial, wraps
import ldap
import logging

import django.db.models
from django.conf import settings
from django.db import connections, router
from django.db.models import signals

import ldapdb  # noqa


logger = logging.getLogger('ldapdb')


def classorinstancemethod(f):
    """
    Decorator that allows the method to be called both on classes
    and object instances, passing the class or object appropriately.
    """
    class wrapper(object):
        @wraps(f)
        def __get__(self, instance, owner):
            return partial(f, instance or owner)
    return wrapper()


class Model(django.db.models.base.Model):
    """
    Base class for all LDAP models.
    """
    dn = django.db.models.fields.CharField(max_length=200)

    # meta-data
    base_dn = None
    bound_alias = None
    search_scope = ldap.SCOPE_SUBTREE
    object_classes = ['top']

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self.saved_pk = self.pk

    @classorinstancemethod
    def build_rdn(self, **kwargs):
        """
        Build the Relative Distinguished Name for this entry.

        When called as a class method, values for all the key fields
        need to be provided. When called as an instance method, values
        for the remaining fields will be obtained from the instance.
        """
        bits = []
        for field in self._meta.fields:
            if not field.db_column:
                continue
            elif field.name in kwargs:
                bits.append("%s=%s" % (field.db_column,
                                       kwargs[field.name]))
            elif field.primary_key:
                if not isinstance(self, Model):
                    raise TypeError(
                        "All keys must be specified when used on a class")
                bits.append("%s=%s" % (field.db_column,
                                       getattr(self, field.name)))
        if not len(bits):
            raise Exception("Could not build Distinguished Name")
        return '+'.join(bits)

    @classorinstancemethod
    def build_dn(self, **kwargs):
        """
        Build the Distinguished Name for this entry.

        When called as a class method, values for all the key fields
        need to be provided. When called as an instance method, values
        for the remaining fields will be obtained from the instance.
        """
        return "%s,%s" % (self.build_rdn(**kwargs), self.base_dn)
        raise Exception("Could not build Distinguished Name")

    def _get_connection(self, using=None):
        """
        Get the proper LDAP connection.
        """
        using = (using or self.bound_alias
                 or router.db_for_write(self.__class__, instance=self))
        return connections[using]

    def delete(self, using=None):
        """
        Delete this entry.
        """
        connection = self._get_connection(using)
        logger.debug("Deleting LDAP entry %s" % self.dn)
        connection.delete_s(self.dn)
        signals.post_delete.send(sender=self.__class__, instance=self)

    def save(self, using=None):
        """
        Saves the current instance.
        """
        connection = self._get_connection(using)
        if not self.dn:
            # create a new entry
            record_exists = False
            entry = [('objectClass', self.object_classes)]
            new_dn = self.build_dn()

            for field in self._meta.fields:
                if not field.db_column:
                    continue
                value = getattr(self, field.name)
                if value:
                    entry.append((field.db_column,
                                  field.get_db_prep_save(
                                      value, connection=connection)))

            logger.debug("Creating new LDAP entry %s" % new_dn)
            connection.add_s(new_dn, entry)

            # update object
            self.dn = new_dn

        else:
            # update an existing entry
            record_exists = True
            modlist = []
            orig = self.__class__.objects.get(pk=self.saved_pk)
            for field in self._meta.fields:
                if not field.db_column:
                    continue
                old_value = getattr(orig, field.name, None)
                new_value = getattr(self, field.name, None)
                if old_value != new_value:
                    if new_value:
                        modlist.append(
                            (ldap.MOD_REPLACE, field.db_column,
                             field.get_db_prep_save(new_value,
                                                    connection=connection)))
                    elif old_value:
                        modlist.append((ldap.MOD_DELETE, field.db_column,
                                        None))

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
    def bind_as(base_class, alias, dn=None, password=None, **kwargs):
        """
        Returns a copy of the current class that is bound to use
        alternate LDAP connection alias.

        If dn or kwargs are specified, settings for the alias will
        be updated with proper DN and password. If kwargs are specified,
        the DN is built from specified fields using build_dn(**kwargs).
        """

        if dn and kwargs:
            raise TypeError('Either dn or kwargs must be specified')

        if dn or kwargs:
            # adding to/updating settings.DATABASES
            if not dn:
                dn = base_class.build_dn(**kwargs)

            # copy remaining settings from the default alias
            if alias not in settings.DATABASES:
                base_alias = router.db_for_write(base_class)
                new_db = copy.deepcopy(settings.DATABASES[base_alias])
                prev_db = None
                settings.DATABASES[alias] = new_db
            else:
                new_db = settings.DATABASES[alias]
                prev_db = copy.deepcopy(new_db)

            new_db['USER'] = dn
            new_db['PASSWORD'] = password or ''

            # close the cached connection since data has changed
            connections[alias].close()
        else:
            # reusing existing alias
            try:
                # disarm restore_alias()
                prev_db = settings.DATABASES[alias]
            except KeyError:
                raise KeyError('Alias %s not in settings.DATABASES'
                               % alias)

        class Meta:
            proxy = True
        name = "%s_%s" % (base_class.__name__, str(alias))
        new_class = type(name, (base_class,), {
            'bound_alias': alias,
            '__module__': base_class.__module__,
            'Meta': Meta,
            '_prev_db': prev_db,
        })
        return new_class

    @classmethod
    def restore_alias(cls):
        """
        Restore settings.DATABASES to state before bind_as().
        """
        if not cls.bound_alias:
            raise TypeError(
                'restore_alias() is meaningful only on class returned '
                'by bind_as()')

        db_alias = settings.DATABASES[cls.bound_alias]
        if cls._prev_db:
            # restore old alias
            db_alias.clear()
            db_alias.update(cls._prev_db)
        else:
            # just clean up username & password
            del db_alias['USER']
            del db_alias['PASSWORD']

        # close the cached connection since data has changed
        connections[cls.bound_alias].close()

    def __enter__(cls):
        if not cls.bound_alias:
            raise TypeError(
                'Context manager interface is meaningful only on class '
                'returned by bind_as()')
        return cls

    def __exit__(cls, exc_type, exc_value, traceback):
        if not cls.bound_alias:
            raise TypeError(
                'Context manager interface is meaningful only on class '
                'returned by bind_as()')
        cls.restore_alias()

    @classmethod
    def scoped(base_class, base_dn):
        """
        Returns a copy of the current class with a different base_dn.
        """
        class Meta:
            proxy = True
        import re
        suffix = re.sub('[=,]', '_', base_dn)
        name = "%s_%s" % (base_class.__name__, str(suffix))
        new_class = type(name, (base_class,), {
            'base_dn': base_dn, '__module__': base_class.__module__,
            'Meta': Meta})
        return new_class

    class Meta:
        abstract = True
