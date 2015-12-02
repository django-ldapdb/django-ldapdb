import django
from django.contrib import admin
if django.VERSION >= (1, 4):
    from django.conf.urls import include, patterns, url
else:
    from django.conf.urls.defaults import include, patterns, url

admin.autodiscover()

if django.VERSION >= (1, 9):
    urlpatterns = [
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', admin.site.urls),
    ]

elif django.VERSION >= (1, 8):
    urlpatterns = [
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', include(admin.site.urls)),
    ]

else:
    urlpatterns = patterns(
        '',
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
        url(r'^admin/', include(admin.site.urls)),
    )
