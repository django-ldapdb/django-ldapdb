# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project


from django.contrib import admin
from examples.models import LdapGroup, LdapUser
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError


class LdapUserAdmin(admin.ModelAdmin):
    exclude = ['dn', 'password', 'photo']
    list_display = ['username', 'first_name', 'last_name', 'email', 'uid']
    search_fields = ['first_name', 'last_name', 'full_name', 'username']


class GroupUserField(forms.ModelMultipleChoiceField):
    def clean(self, value):
        return value


class LdapGroupForm(forms.ModelForm):
    usernames = GroupUserField(queryset=LdapUser.objects.all(),
                               widget=FilteredSelectMultiple('Users', is_stacked=False),
                               required=True, to_field_name='dn')

    class Meta:
        exclude = []
        model = LdapGroup

    def clean_usernames(self):
        data = self.cleaned_data['usernames']
        if not data:
            raise ValidationError(_('Enter a list of values.'), code='list')
        return data


class LdapGroupAdmin(admin.ModelAdmin):
    form = LdapGroupForm
    exclude = ['dn', 'usernames']
    list_display = ['name', 'gid', 'usernames']
    search_fields = ['name']


admin.site.register(LdapGroup, LdapGroupAdmin)
admin.site.register(LdapUser, LdapUserAdmin)
