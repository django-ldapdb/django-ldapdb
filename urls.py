import django


from django.contrib import admin

admin.autodiscover()

if django.VERSION[:2] <= (1, 7):
    from django.conf.urls import include, patterns, url
    urlpatterns = patterns('',
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', include(admin.site.urls)),
    )

else:
    from django.conf.urls import include, url
    urlpatterns = [
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', include(admin.site.urls)),
    ]
