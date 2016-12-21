# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project


from django.contrib import admin
from examples.models import LdapGroup, LdapUser


class LdapGroupAdmin(admin.ModelAdmin):
    exclude = ['dn', 'usernames']
    list_display = ['name', 'gid']
    search_fields = ['name']


class LdapUserAdmin(admin.ModelAdmin):
    exclude = ['dn', 'password', 'photo']
    list_display = ['username', 'first_name', 'last_name', 'email', 'uid']
    search_fields = ['first_name', 'last_name', 'full_name', 'username']


admin.site.register(LdapGroup, LdapGroupAdmin)
admin.site.register(LdapUser, LdapUserAdmin)
