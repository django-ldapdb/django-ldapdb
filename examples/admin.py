# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

from django.contrib import admin
from examples.models import LdapGroup, LdapUser
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple


class LdapUserAdmin(admin.ModelAdmin):
    exclude = ['dn', 'password', 'photo']
    list_display = ['username', 'first_name', 'last_name', 'email', 'uid']
    search_fields = ['first_name', 'last_name', 'full_name', 'username']


class LdapGroupForm(forms.ModelForm):
    usernames = forms.ModelMultipleChoiceField(queryset=LdapUser.objects.all(),
                                               widget=FilteredSelectMultiple('Users', is_stacked=False),
                                               required=False)

    class Meta:
        exclude = []
        model = LdapGroup

    def clean_usernames(self):
        data = self.cleaned_data['usernames']
        if not data:
            return []
        return list(data.values_list('username', flat=True))


class LdapGroupAdmin(admin.ModelAdmin):
    form = LdapGroupForm
    exclude = ['dn', 'usernames']
    list_display = ['name', 'gid', 'usernames']
    search_fields = ['name']


admin.site.register(LdapGroup, LdapGroupAdmin)
admin.site.register(LdapUser, LdapUserAdmin)
