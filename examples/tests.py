# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from __future__ import unicode_literals

import time

import factory
import factory.django
import factory.fuzzy
import volatildap
from django.conf import settings
from django.contrib.auth import hashers as auth_hashers
from django.contrib.auth import models as auth_models
from django.core import management
from django.db import connections
from django.db.models import Count, Q
from django.test import TestCase
from django.utils import timezone

from examples.models import LdapGroup, LdapMultiPKRoom, LdapUser
from ldapdb.backends.ldap.compiler import SQLCompiler, query_as_ldap

groups = ('ou=groups,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
people = ('ou=people,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
contacts = ('ou=contacts,ou=groups,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
rooms = ('ou=rooms,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['rooms']})
foogroup = ('cn=foogroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['foouser', 'baruser'],
    'gidNumber': ['1000'], 'cn': ['foogroup']})
bargroup = ('cn=bargroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['zoouser', 'baruser'],
    'gidNumber': ['1001'], 'cn': ['bargroup']})
wizgroup = ('cn=wizgroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['wizuser', 'baruser'],
    'gidNumber': ['1002'], 'cn': ['wizgroup']})
foouser = ('uid=foouser,ou=people,dc=example,dc=org', {
    'cn': [b'F\xc3\xb4o Us\xc3\xa9r'],
    'objectClass': ['posixAccount', 'shadowAccount', 'inetOrgPerson'],
    'loginShell': ['/bin/bash'],
    'jpegPhoto': [
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff'
        b'\xfe\x00\x1cCreated with GIMP on a Mac\xff\xdb\x00C\x00\x05\x03\x04'
        b'\x04\x04\x03\x05\x04\x04\x04\x05\x05\x05\x06\x07\x0c\x08\x07\x07\x07'
        b'\x07\x0f\x0b\x0b\t\x0c\x11\x0f\x12\x12\x11\x0f\x11\x11\x13\x16\x1c'
        b'\x17\x13\x14\x1a\x15\x11\x11\x18!\x18\x1a\x1d\x1d\x1f\x1f\x1f\x13'
        b'\x17"$"\x1e$\x1c\x1e\x1f\x1e\xff\xdb\x00C\x01\x05\x05\x05\x07\x06\x07'
        b'\x0e\x08\x08\x0e\x1e\x14\x11\x14\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\xff\xc0\x00\x11\x08\x00\x08\x00\x08\x03'
        b'\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00'
        b'\x19\x10\x00\x03\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x01\x02\x06\x11A\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x11\x01'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff'
        b'\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\x9d\xf29wU5Q\xd6'
        b'\xfd\x00\x01\xff\xd9'],
    'uidNumber': ['2000'], 'gidNumber': ['1000'], 'sn': [b'Us\xc3\xa9r'],
    'homeDirectory': ['/home/foouser'], 'givenName': [b'F\xc3\xb4o'],
    'uid': ['foouser']})


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Faker('username')
    email = factory.Faker('email')
    is_active = True
    password = factory.LazyAttribute(lambda o: auth_hashers.make_password(o.cleartext_password))

    class Meta:
        model = auth_models.User

    class Params:
        cleartext_password = factory.fuzzy.FuzzyText(30)
        superuser = factory.Trait(
            is_staff=True,
            is_superuser=True,
        )


class BaseTestCase(TestCase):
    directory = {}

    @classmethod
    def setUpClass(cls):
        super(BaseTestCase, cls).setUpClass()
        cls.ldap_server = volatildap.LdapServer(
            initial_data=cls.directory,
            schemas=['core.schema', 'cosine.schema', 'inetorgperson.schema', 'nis.schema'],
        )
        settings.DATABASES['ldap']['USER'] = cls.ldap_server.rootdn
        settings.DATABASES['ldap']['PASSWORD'] = cls.ldap_server.rootpw
        settings.DATABASES['ldap']['NAME'] = cls.ldap_server.uri

    @classmethod
    def tearDownClass(cls):
        cls.ldap_server.stop()
        super(BaseTestCase, cls).tearDownClass()

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.ldap_server.start()


class ConnectionTestCase(BaseTestCase):
    directory = dict([people, foouser])

    def test_system_checks(self):
        management.call_command('check')

    def test_make_migrations(self):
        management.call_command('makemigrations', dry_run=True)

    def test_connection_options(self):
        LdapUser.objects.get(username='foouser')
        # self.assertEqual(self.ldapobj.get_option(ldap.OPT_X_TLS_DEMAND), True)

    def test_start_tls(self):
        # self.assertFalse(self.ldapobj.tls_enabled)
        LdapUser.objects.get(username='foouser')

    def test_bound_as_admin(self):
        LdapUser.objects.get(username='foouser')
        # self.assertEqual(self.ldapobj.bound_as, admin[0])


class GroupTestCase(BaseTestCase):
    directory = dict([groups, foogroup, bargroup, wizgroup, people, foouser])

    def test_count_none(self):
        qs = LdapGroup.objects.none()
        self.assertEqual(qs.count(), 0)

    def test_count_all(self):
        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 3)

    def test_aggregate_count(self):
        qs = LdapGroup.objects.all()
        result = qs.aggregate(num_groups=Count('name'))
        self.assertEqual(result['num_groups'], 3)

    def test_annotate_count(self):
        groups = LdapGroup.objects.order_by('name').annotate(num_usernames=Count('usernames'))
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0].name, 'bargroup')
        self.assertEqual(groups[0].num_usernames, 2)
        self.assertEqual(groups[1].name, 'foogroup')
        self.assertEqual(groups[1].num_usernames, 2)
        self.assertEqual(groups[2].name, 'wizgroup')
        self.assertEqual(groups[2].num_usernames, 2)
        groups = LdapGroup.objects.filter(name='foogroup').annotate(num_usernames=Count('usernames'))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, 'foogroup')
        self.assertEqual(groups[0].num_usernames, 2)
        groups = LdapGroup.objects.annotate(num_usernames=Count('usernames')).filter(name='foogroup')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, 'foogroup')
        self.assertEqual(groups[0].num_usernames, 2)

    def test_length_all(self):
        qs = LdapGroup.objects.all()
        self.assertEqual(len(qs), 3)

    def test_length_none(self):
        qs = LdapGroup.objects.none()
        self.assertEqual(len(qs), 0)

    def test_ldap_filter(self):
        def get_filterstr(qs):
            connection = connections['ldap']
            compiler = SQLCompiler(
                query=qs.query,
                connection=connection,
                using=None,
            )
            return query_as_ldap(qs.query, compiler, connection).filterstr

        # single filter
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEqual(get_filterstr(qs), '(&(objectClass=posixGroup)(cn=foogroup))')

        qs = LdapGroup.objects.filter(Q(name='foogroup'))
        self.assertEqual(get_filterstr(qs), '(&(objectClass=posixGroup)(cn=foogroup))')

        # AND filter
        qs = LdapGroup.objects.filter(gid=1000, name='foogroup')
        self.assertIn(get_filterstr(qs), [
            '(&(objectClass=posixGroup)(&(gidNumber=1000)(cn=foogroup)))',
            '(&(objectClass=posixGroup)(&(cn=foogroup)(gidNumber=1000)))',
        ])

        qs = LdapGroup.objects.filter(Q(gid=1000) & Q(name='foogroup'))
        self.assertIn(get_filterstr(qs), [
            '(&(objectClass=posixGroup)(&(gidNumber=1000)(cn=foogroup)))',
            '(&(objectClass=posixGroup)(&(cn=foogroup)(gidNumber=1000)))',
        ])

        # OR filter
        qs = LdapGroup.objects.filter(Q(gid=1000) | Q(name='foogroup'))
        self.assertIn(get_filterstr(qs), [
            '(&(objectClass=posixGroup)(|(gidNumber=1000)(cn=foogroup)))',
            '(&(objectClass=posixGroup)(|(cn=foogroup)(gidNumber=1000)))',
        ])

        # single exclusion
        qs = LdapGroup.objects.exclude(name='foogroup')
        self.assertEqual(get_filterstr(qs), '(&(objectClass=posixGroup)(!(cn=foogroup)))')

        qs = LdapGroup.objects.filter(~Q(name='foogroup'))
        self.assertEqual(get_filterstr(qs), '(&(objectClass=posixGroup)(!(cn=foogroup)))')

        # multiple exclusion
        qs = LdapGroup.objects.exclude(name='foogroup', gid=1000)
        self.assertIn(get_filterstr(qs), [
            '(&(objectClass=posixGroup)(!(&(gidNumber=1000)(cn=foogroup))))',
            '(&(objectClass=posixGroup)(!(&(cn=foogroup)(gidNumber=1000))))',
        ])

        qs = LdapGroup.objects.filter(name='foogroup').exclude(gid=1000)
        self.assertIn(get_filterstr(qs), [
            '(&(objectClass=posixGroup)(&(cn=foogroup)(!(gidNumber=1000))))',
            '(&(objectClass=posixGroup)(&(!(gidNumber=1000))(cn=foogroup)))',
        ])

    def test_filter(self):
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEqual(qs.count(), 1)

        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEqual(len(qs), 1)

        g = qs[0]
        self.assertEqual(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEqual(g.name, 'foogroup')
        self.assertEqual(g.gid, 1000)
        self.assertCountEqual(g.usernames, ['foouser', 'baruser'])

        # try to filter non-existent entries
        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEqual(qs.count(), 0)

        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEqual(len(qs), 0)

    def test_get(self):
        g = LdapGroup.objects.get(name='foogroup')
        self.assertEqual(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEqual(g.name, 'foogroup')
        self.assertEqual(g.gid, 1000)
        self.assertCountEqual(g.usernames, ['foouser', 'baruser'])

        # try to get a non-existent entry
        self.assertRaises(LdapGroup.DoesNotExist, LdapGroup.objects.get,
                          name='does_not_exist')

    def test_exists(self):
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertTrue(qs.exists())

        qs2 = LdapGroup.objects.filter(name='missing')
        self.assertFalse(qs2.exists())

    def test_get_by_dn(self):
        g = LdapGroup.objects.get(dn='cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEqual(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEqual(g.name, 'foogroup')
        self.assertEqual(g.gid, 1000)
        self.assertCountEqual(g.usernames, ['foouser', 'baruser'])

    def test_gid_lookup(self):
        g = LdapGroup.objects.get(gid__in=[1000, 2000, 3000])
        self.assertEqual(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEqual(g.name, 'foogroup')
        self.assertEqual(g.gid, 1000)
        self.assertCountEqual(g.usernames, ['foouser', 'baruser'])

    def test_insert(self):
        g = LdapGroup()
        g.name = 'newgroup'
        g.gid = 1010
        g.usernames = ['someuser', 'foouser']
        g.save()

        # check group was created
        new = LdapGroup.objects.get(name='newgroup')
        self.assertEqual(new.name, 'newgroup')
        self.assertEqual(new.gid, 1010)
        self.assertCountEqual(new.usernames, ['someuser', 'foouser'])

    def test_create(self):
        LdapGroup.objects.create(
            name='newgroup',
            gid=1010,
            usernames=['someuser', 'foouser'],
        )

        # check group was created
        new = LdapGroup.objects.get(name='newgroup')
        self.assertEqual(new.name, 'newgroup')
        self.assertEqual(new.gid, 1010)
        self.assertCountEqual(new.usernames, ['someuser', 'foouser'])

    def test_order_by(self):
        # ascending name
        qs = LdapGroup.objects.order_by('name')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'bargroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'wizgroup')

        # descending name
        qs = LdapGroup.objects.order_by('-name')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'wizgroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'bargroup')

        # ascending gid
        qs = LdapGroup.objects.order_by('gid')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].gid, 1000)
        self.assertEqual(qs[1].gid, 1001)
        self.assertEqual(qs[2].gid, 1002)

        # descending gid
        qs = LdapGroup.objects.order_by('-gid')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].gid, 1002)
        self.assertEqual(qs[1].gid, 1001)
        self.assertEqual(qs[2].gid, 1000)

        # ascending pk
        qs = LdapGroup.objects.order_by('pk')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'bargroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'wizgroup')

        # descending pk
        qs = LdapGroup.objects.order_by('-pk')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'wizgroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'bargroup')

        # ascending dn
        qs = LdapGroup.objects.order_by('dn')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'bargroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'wizgroup')

        # descending dn
        qs = LdapGroup.objects.order_by('-dn')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'wizgroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'bargroup')

    def test_bulk_delete(self):
        LdapGroup.objects.all().delete()

        qs = LdapGroup.objects.all()
        self.assertEqual(len(qs), 0)

    def test_bulk_delete_none(self):
        LdapGroup.objects.none().delete()

        qs = LdapGroup.objects.all()
        self.assertEqual(len(qs), 3)

    def test_slice(self):
        qs = LdapGroup.objects.order_by('gid')
        objs = list(qs)
        self.assertEqual(len(objs), 3)
        self.assertEqual(objs[0].gid, 1000)
        self.assertEqual(objs[1].gid, 1001)
        self.assertEqual(objs[2].gid, 1002)

        # limit only
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[:2]
        self.assertEqual(objs.count(), 2)

        objs = qs[:2]
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].gid, 1000)
        self.assertEqual(objs[1].gid, 1001)

        # offset only
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[1:]
        self.assertEqual(objs.count(), 2)

        objs = qs[1:]
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].gid, 1001)
        self.assertEqual(objs[1].gid, 1002)

        # offset and limit
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[1:2]
        self.assertEqual(objs.count(), 1)

        objs = qs[1:2]
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].gid, 1001)

    def test_update(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.gid = 1002
        g.usernames = ['foouser2', u'baruseeer2']
        g.save()

        # check group was updated
        new = LdapGroup.objects.get(name='foogroup')
        self.assertEqual(new.name, 'foogroup')
        self.assertEqual(new.gid, 1002)
        self.assertCountEqual(new.usernames, ['foouser2', u'baruseeer2'])

    def test_update_change_dn(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.name = 'foogroup2'
        g.save()
        self.assertEqual(g.dn, 'cn=foogroup2,%s' % LdapGroup.base_dn)

        # check group was updated
        new = LdapGroup.objects.get(name='foogroup2')
        self.assertEqual(new.name, 'foogroup2')
        self.assertEqual(new.gid, 1000)
        self.assertCountEqual(new.usernames, ['foouser', 'baruser'])

    def test_values(self):
        qs = sorted(LdapGroup.objects.values_list('name', flat=True))
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0], 'bargroup')
        self.assertEqual(qs[1], 'foogroup')
        self.assertEqual(qs[2], 'wizgroup')

    def test_search(self):
        qs = sorted(LdapGroup.objects.filter(name__contains='foo'))
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].name, 'foogroup')

    def test_values_list(self):
        qs = sorted(LdapGroup.objects.values_list('name'))
        self.assertEqual(len(qs), 3)
        self.assertEqual(list(qs[0]), ['bargroup'])
        self.assertEqual(list(qs[1]), ['foogroup'])
        self.assertEqual(list(qs[2]), ['wizgroup'])

    def test_delete(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.delete()

        qs = LdapGroup.objects.all()
        self.assertEqual(len(qs), 2)

    def test_paginated_search(self):
        # This test will change the settings, assert we don't break things
        self.assertIsNone(settings.DATABASES['ldap'].get('CONNECTION_OPTIONS', {}).get('page_size'))

        # Test without BATCH_SIZE
        qs = LdapGroup.objects.filter(name__contains='group').order_by('name')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'bargroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'wizgroup')

        # Set new page size
        settings.DATABASES['ldap']['CONNECTION_OPTIONS'] = settings.DATABASES['ldap'].get('CONNECTION_OPTIONS', {})
        settings.DATABASES['ldap']['CONNECTION_OPTIONS']['page_size'] = 1
        connections['ldap'].close()  # Force connection reload

        qs = LdapGroup.objects.filter(name__contains='group').order_by('name')
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[0].name, 'bargroup')
        self.assertEqual(qs[1].name, 'foogroup')
        self.assertEqual(qs[2].name, 'wizgroup')

        # Restore previous configuration
        del settings.DATABASES['ldap']['CONNECTION_OPTIONS']['page_size']

    def test_listfield_manipulation(self):
        g = LdapGroup.objects.get(name='foogroup')
        self.assertCountEqual(['foouser', 'baruser'], g.usernames)

        # Replace values, with duplicated.
        g.usernames = ['john', 'jane', 'john']
        g.save()
        g = LdapGroup.objects.get(name='foogroup')
        self.assertCountEqual(['john', 'jane'], g.usernames)

        # Clear values
        g.usernames = []
        g.save()
        g = LdapGroup.objects.get(name='foogroup')
        self.assertEqual([], g.usernames)


class UserTestCase(BaseTestCase):
    directory = dict([groups, people, foouser])

    def test_verbose_name(self):
        self.assertEqual("Prime name", LdapUser._meta.get_field('first_name').verbose_name)
        self.assertEqual("Final name", LdapUser._meta.get_field('last_name').verbose_name)

    def test_get(self):
        u = LdapUser.objects.get(username='foouser')
        self.assertEqual(u.first_name, u'Fôo')
        self.assertEqual(u.last_name, u'Usér')
        self.assertEqual(u.full_name, u'Fôo Usér')

        self.assertEqual(u.group, 1000)
        self.assertEqual(u.home_directory, '/home/foouser')
        self.assertEqual(u.uid, 2000)
        self.assertEqual(u.username, 'foouser')
        self.assertEqual(
            u.photo,
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01'
            b'\x01\x00H\x00H\x00\x00\xff\xfe\x00\x1cCreated with '
            b'GIMP on a Mac\xff\xdb\x00C\x00\x05\x03\x04\x04\x04'
            b'\x03\x05\x04\x04\x04\x05\x05\x05\x06\x07\x0c\x08'
            b'\x07\x07\x07\x07\x0f\x0b\x0b\t\x0c\x11\x0f\x12\x12'
            b'\x11\x0f\x11\x11\x13\x16\x1c\x17\x13\x14\x1a\x15'
            b'\x11\x11\x18!\x18\x1a\x1d\x1d\x1f\x1f\x1f\x13\x17'
            b'"$"\x1e$\x1c\x1e\x1f\x1e\xff\xdb\x00C\x01\x05\x05'
            b'\x05\x07\x06\x07\x0e\x08\x08\x0e\x1e\x14\x11\x14'
            b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
            b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
            b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
            b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
            b'\x1e\x1e\xff\xc0\x00\x11\x08\x00\x08\x00\x08\x03'
            b'\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15'
            b'\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x19\x10'
            b'\x00\x03\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x01\x02\x06\x11A\xff\xc4\x00'
            b'\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x11'
            b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00'
            b'\x02\x11\x03\x11\x00?\x00\x9d\xf29wU5Q\xd6\xfd\x00'
            b'\x01\xff\xd9',
        )

        self.assertRaises(LdapUser.DoesNotExist, LdapUser.objects.get,
                          username='does_not_exist')

    def test_update(self):
        # slapd removes microsecond details.
        before = timezone.now().replace(microsecond=0)

        u = LdapUser.objects.get(username='foouser')
        u.first_name = u'Fôo2'
        u.save()

        after = timezone.now().replace(microsecond=0)

        self.assertLessEqual(before, u.last_modified)
        self.assertLessEqual(u.last_modified, after)

        # make sure DN gets updated if we change the pk
        u.username = 'foouser2'
        u.save()
        self.assertEqual(u.dn, 'uid=foouser2,%s' % LdapUser.base_dn)

    def test_charfield_empty_values(self):
        """CharField should accept empty values."""
        u = LdapUser.objects.get(username='foouser')
        # Both '' and None are accepted
        u.phone = ''
        u.mobile_phone = None
        u.save()

        # '' and None are normalized to ''.
        u2 = LdapUser.objects.get(dn=u.dn)
        self.assertEqual('', u2.phone)
        self.assertEqual('', u2.mobile_phone)

    def test_intfield_empty_value(self):
        u = LdapUser.objects.get(username='foouser')
        # Set to 0
        u.uid = 0
        u.save()

        # Ensure we still fetch a '0', not an empty ID.
        u2 = LdapUser.objects.get(dn=u.dn)
        self.assertEqual(0, u2.uid)

    def test_datetime_lookup(self):

        # Due to slapd ignoring microsecond in last_modified,
        # wait for one second to ensure that all timestamps are on the proper
        # side of the 'before' boundary.
        time.sleep(1)
        before = timezone.now().replace(microsecond=0)

        qs = LdapUser.objects.filter(last_modified__gte=before)
        self.assertEqual([], list(qs))

        u = LdapUser.objects.get(username='foouser')
        u.first_name = u"Foo2"
        u.save()

        u = LdapUser.objects.get(username='foouser')
        self.assertLessEqual(before, u.last_modified)

        qs = LdapUser.objects.filter(last_modified__gte=before)
        self.assertEqual([u], list(qs))


class ScopedTestCase(BaseTestCase):
    directory = dict([groups, people, foogroup, contacts])

    def setUp(self):
        super(ScopedTestCase, self).setUp()
        self.scoped_model = LdapGroup.scoped("ou=contacts,%s" %
                                             LdapGroup.base_dn)

    def test_scope(self):
        ScopedGroup = self.scoped_model

        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 1)

        qs = ScopedGroup.objects.all()
        self.assertEqual(qs.count(), 0)

        # create scoped group
        g2 = ScopedGroup()
        g2.name = "scopedgroup"
        g2.gid = 5000
        g2.save()

        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 2)

        qs = ScopedGroup.objects.all()
        self.assertEqual(qs.count(), 1)

        g2 = ScopedGroup.objects.get(name="scopedgroup")
        self.assertEqual(g2.name, u'scopedgroup')
        self.assertEqual(g2.gid, 5000)


class CompositePKTests(BaseTestCase):
    directory = dict([rooms])

    def test_create(self):
        room = LdapMultiPKRoom(
            name="Director office",
            number="42.01",
        )
        room.save()
        room = LdapMultiPKRoom.objects.get()
        self.assertEqual("cn=Director office+roomNumber=42.01,ou=rooms,dc=example,dc=org", room.dn)

    def test_fetch(self):
        room = LdapMultiPKRoom(
            name="Director office",
            number="42.01",
        )
        room.save()

        room2 = LdapMultiPKRoom.objects.get(number="42.01")
        self.assertEqual("Director office", room2.name)
        self.assertEqual("42.01", room2.number)

    def test_move(self):
        room = LdapMultiPKRoom.objects.create(
            name="Director office",
            number="42.01",
        )

        room.number = "42.02"
        room.save()

        qs = LdapMultiPKRoom.objects.all()
        self.assertEqual(1, len(qs))
        new_room = qs.get()
        self.assertEqual(room, new_room)
        self.assertEqual("42.02", new_room.number)
        self.assertEqual("cn=Director office+roomNumber=42.02,ou=rooms,dc=example,dc=org", new_room.dn)

    def test_update(self):
        room = LdapMultiPKRoom.objects.create(
            name="Director office",
            number="42.01",
            phone='+001234',
        )

        room.phone = '+004444'
        room.save()

        qs = LdapMultiPKRoom.objects.all()
        self.assertEqual(1, len(qs))
        new_room = qs.get()
        self.assertEqual(room, new_room)
        self.assertEqual("42.01", new_room.number)
        self.assertEqual('+004444', new_room.phone)
        self.assertEqual("cn=Director office+roomNumber=42.01,ou=rooms,dc=example,dc=org", new_room.dn)

    def test_update_ambiguous_pk(self):
        """Updating an object where two entries with close pks exist shouldn't fail.

        See #159.
        """
        room1 = LdapMultiPKRoom.objects.create(
            name="Director office",
            number="42.01",
            phone='+001234',
        )
        LdapMultiPKRoom.objects.create(
            name="Director office",
            number="42.01b",
            phone='+001111',
        )

        room1.phone = '+004444'
        room1.save()

        qs = LdapMultiPKRoom.objects.all()
        self.assertEqual(2, len(qs))
        new_room = qs.get(number="42.01")
        self.assertEqual("42.01", new_room.number)
        self.assertEqual('+004444', new_room.phone)
        self.assertEqual("cn=Director office+roomNumber=42.01,ou=rooms,dc=example,dc=org", new_room.dn)


class AdminTestCase(BaseTestCase):
    directory = dict([groups, people, foouser, foogroup, bargroup])

    def setUp(self):
        super(AdminTestCase, self).setUp()
        self._user = UserFactory(
            username='test_user',
            cleartext_password='password',
            superuser=True,
        )
        self.client.login(username="test_user", password="password")

    def test_index(self):
        response = self.client.get('/admin/examples/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "Ldap users")

    def test_group_list(self):
        response = self.client.get('/admin/examples/ldapgroup/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by name
        response = self.client.get('/admin/examples/ldapgroup/?o=1')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by gid
        response = self.client.get('/admin/examples/ldapgroup/?o=2')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_detail(self):
        response = self.client.get('/admin/examples/ldapgroup/foogroup/', follow=True)
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_add(self):
        response = self.client.post('/admin/examples/ldapgroup/add/',
                                    {'gid': '1002', 'name': 'wizgroup'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 3)

    def test_group_delete(self):
        response = self.client.post(
            '/admin/examples/ldapgroup/foogroup/delete/', {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 1)

    def test_group_search(self):
        response = self.client.get('/admin/examples/ldapgroup/?q=foo')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_user_list(self):
        response = self.client.get('/admin/examples/ldapuser/')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by username
        response = self.client.get('/admin/examples/ldapuser/?o=1')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by uid
        response = self.client.get('/admin/examples/ldapuser/?o=2')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_detail(self):
        response = self.client.get('/admin/examples/ldapuser/foouser/', follow=True)
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_delete(self):
        response = self.client.post('/admin/examples/ldapuser/foouser/delete/',
                                    {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapuser/')
