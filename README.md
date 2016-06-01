django-ldapdb - support for django models over LDAP  
Copyright (c) 2009-2011, Bolloré Telecom  
Copyright (c) 2013, Jeremy Lainé

[![Build Status](https://travis-ci.org/django-ldapdb/django-ldapdb.png)](https://travis-ci.org/django-ldapdb/django-ldapdb)

About
-----

_django-ldapdb_ is an LDAP database backend for Django. It allows you to
manipulate LDAP entries using Django's models. Declaring models using the
LDAP backend is very straightforward, you simply inherit from
_ldapdb.models.Model_ and declare the fields in the same way as for regular
models. You can even edit the LDAP entries using Django's admin interface.

_django-ldapdb_ requires Django version 1.2.x, 1.3.x, 1.4.x, 1.5.x, 1.6.x,
1.7.x or 1.8.x.

_django-ldapdb_ is distributed under the BSD license, see the LICENSE
file for details. See AUTHORS file for a full list of contributors.

Using django-ldapdb
-------------------

Add the following to your _settings.py_:

    DATABASES = {
        ...
        'ldap': {
            'ENGINE': 'ldapdb.backends.ldap',
            'NAME': 'ldap://ldap.nodomain.org/',
            'USER': 'cn=admin,dc=nodomain,dc=org',
            'PASSWORD': 'some_secret_password',
         }
     }
    DATABASE_ROUTERS = ['ldapdb.router.Router']

If you want to access posixGroup entries in your application, you can add
something like this to your _models.py_:

    from ldapdb.models.fields import CharField, IntegerField, ListField
    import ldapdb.models

    class LdapGroup(ldapdb.models.Model):
        """
        Class for representing an LDAP group entry.
        """
        # LDAP meta-data
        base_dn = "ou=groups,dc=nodomain,dc=org"
        object_classes = ['posixGroup']

        # posixGroup attributes
        gid = IntegerField(db_column='gidNumber', unique=True)
        name = CharField(db_column='cn', max_length=200, primary_key=True)
        members = ListField(db_column='memberUid')

        def __str__(self):
            return self.name

        def __unicode__(self):
            return self.name

_Important note_ : you _must_ declare an attribute to be used as the primary
key. This attribute will play a special role, as it will be used to build the
Relative Distinguished Name of the entry. For instance in the example above,
a group whose cn is _foo_ will have the DN _cn=foo,ou=groups,dc=nodomain,dc=org_.
