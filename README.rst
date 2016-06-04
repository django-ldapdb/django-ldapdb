django-ldapdb
=============

.. image:: https://secure.travis-ci.org/django-ldapdb/django-ldapdb.png?branch=master
    :target: http://travis-ci.org/django-ldapdb/django-ldapdb/

.. image:: https://img.shields.io/pypi/v/django-ldapdb.svg
    :target: https://pypi.python.org/pypi/django-ldapdb/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/pyversions/django-ldapdb.svg
    :target: https://pypi.python.org/pypi/django-ldapdb/
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/wheel/django-ldapdb.svg
    :target: https://pypi.python.org/pypi/django-ldapdb/
    :alt: Wheel status

.. image:: https://img.shields.io/pypi/l/django-ldapdb.svg
    :target: https://pypi.python.org/pypi/django-ldapdb/
    :alt: License


``django-ldapdb`` is an LDAP database backend for Django, allowing to manipulate
LDAP entries through Django models.

It supports most of the same APIs as a Django model:

* ``MyModel.objects.create()``
* ``MyModel.objects.filter(x=1, y__contains=2)``
* Full admin support and browsing


``django-ldapdb`` supports Django versions 1.7 to 1.9, and Python 2.7/3.4/3.5.


Using django-ldapdb
-------------------

Add the following to your ``settings.py``:

.. code-block:: python

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
something like this to your ``models.py``:


.. code-block:: python

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


**Important note:**
    You **must** declare an attribute to be used as the primary key.
    This attribute will play a special role, as it will be used to build
    the Relative Distinguished Name of the entry.
    
    For instance in the example above, a group whose cn is ``foo``
    will have the DN ``cn=foo,ou=groups,dc=nodomain,dc=org``.
