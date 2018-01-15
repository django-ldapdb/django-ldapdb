# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

import django

from django.conf.urls import include, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = [
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls) if django.VERSION[:2] < (1, 9) else admin.site.urls),
]
