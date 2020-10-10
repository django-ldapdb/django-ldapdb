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


``django-ldapdb`` supports every upstream-supported Django version, based on
the `Django support policy <https://www.djangoproject.com/download/#supported-versions>`_.

For the current version, the following versions are supported:

- Django 2.2 (LTS), under Python 3.6 - 3.8 (Python 3.5 has reached its end of life);
- Django 3.0, under Python 3.6 - 3.8;
- Django 3.1, under Python 3.6 - 3.8.


Installing django-ldapdb
------------------------

Linux
~~~~~

Use pip: ``pip install django-ldapdb``

You might also need the usual ``LDAP`` packages from your distribution, usually named ``openldap`` or ``ldap-utils``.


Windows
~~~~~~~

``django-ldapdb`` depends on the `python-ldap <https://pypi.python.org/pypi/python-ldap>` project.
Either follow `its Windows installation guide <https://www.python-ldap.org/en/latest/installing.html>`_,
or install a pre-built version from https://www.lfd.uci.edu/~gohlke/pythonlibs/#python-ldap
(choose the ``.whl`` file matching your Python/Windows combination, and install it with ``pip install python-ldap-3...whl``).

You may then install ``django-ldapdb`` with

``pip install django-ldapdb``


Using django-ldapdb
-------------------

Add the following to your ``settings.py``:

.. code-block:: python

    DATABASES = {
        'ldap': {
            'ENGINE': 'ldapdb.backends.ldap',
            'NAME': 'ldap://ldap.nodomain.org/',
            'USER': 'cn=admin,dc=nodomain,dc=org',
            'PASSWORD': 'some_secret_password',
         },
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
         },
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

and add this to your ``admin.py``:

.. code-block:: python

    from django.contrib import admin
    from . import models

    class LDAPGroupAdmin(admin.ModelAdmin):
        exclude = ['dn', 'objectClass']
        list_display = ['gid', 'name']

    admin.site.register(models.LDAPGroup, LDAPGroupAdmin)


**Important note:**
    You **must** declare an attribute to be used as the primary key.
    This attribute will play a special role, as it will be used to build
    the Relative Distinguished Name of the entry.
    
    For instance in the example above, a group whose cn is ``foo``
    will have the DN ``cn=foo,ou=groups,dc=nodomain,dc=org``.


Supported fields
----------------

djanglo-ldapdb provides the following fields, all imported from ``ldapdb.models.fields``:

Similar to Django:

    * ``IntegerField``
    * ``FloatField``
    * ``BooleanField``
    * ``CharField``
    * ``ImageField``
    * ``DateTimeField``

Specific to a LDAP server:
    * ``ListField`` (holds a list of text values)
    * ``TimestampField`` (Stores a datetime as a posix timestamp, typically for posixAccount)

Legacy:
    * ``DateField`` (Stores a date in an arbitrary format. A LDAP server has no notion of ``Date``).


Tuning django-ldapdb
--------------------

It is possible to adjust django-ldapdb's behavior by defining a few parameters in the ``DATABASE`` section:

``PAGE_SIZE`` (default: ``1000``)
    Define the maximum size of a results page to be returned by the server

``QUERY_TIMEOUT`` (default: no limit)
    Define the maximum time in seconds we'll wait to get a reply from the server (on a per-query basis).

    .. note:: This setting applies on individual requests; if a high-level operation requires many
              queries (for instance a paginated search yielding thousands of entries),
              the timeout will be used on each individual request;
              the overall processing time might be much higher.


Developing with a LDAP server
-----------------------------

When developing against a LDAP server, having access to a development LDAP server often proves
useful.

django-ldapdb uses the `volatildap project <https://pypi.org/project/volatildap>`_ for this purpose:

- A LDAP server is instantiated for each TestClass;
- Its content is reset at the start of each test function;
- It can be customized to embark any schemas required by the application;
- Starting with volatildap 1.4.0, the volatildap server can be controlled remotely, avoiding the need
  to install a LDAP server on the host.

Applications using django-ldapdb may use the following code snippet when setting up their tests:

.. code-block:: python

    # This snippet is released in the Public Domain

    from django.conf import settings
    from django.test import TestCase

    import volatildap

    class LdapEnabledTestCase(TestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            cls.ldap = volatildap.LdapServer(
                # Load some initial data
                initial={'ou=people': {
                    'ou': ['people'],
                    'objectClass': ['organizationalUnit'],
                }},
                # Enable more LDAP schemas
                schemas=['core.schema', 'cosine.schema', 'inetorgperson.schema', 'nis.schema'],
            )
            # The volatildap server uses specific defaults, and listens on an arbitrary port.
            # Copy the server-side values to Django settings
            settings.DATABASES['ldap']['USER'] = cls.ldap.rootdn
            settings.DATABASES['ldap']['PASSWORD'] = cls.ldap.rootpw
            settings.DATABASES['ldap']['NAME'] = cls.ldap.uri

        def setUp(self):
            super().setUp()
            # Starting an already-started volatildap server performs a data reset
            self.ldap.start()

        @classmethod
        def tearDownClass(cls):
            # Free up resources on teardown.
            cls.ldap.stop()
            super().tearDownClass()
