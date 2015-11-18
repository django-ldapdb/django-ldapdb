try:
    # django >= 1.4
    from django.conf.urls import include, patterns, url
except ImportError:
    # django < 1.4
    # TODO: Versions unsupported by Django, this can be removed.
    from django.conf.urls.defaults import include, patterns, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
)
