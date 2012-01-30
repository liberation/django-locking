from django.conf.urls.defaults import *

urlpatterns = patterns('locking.views',
        (r'(?P<app>[\w-]+)/(?P<model>[\w-]+)/(?P<id>\d+)/unlock/$', 'unlock'),
        (r'(?P<app>[\w-]+)/(?P<model>[\w-]+)/(?P<id>\d+)/refresh_lock/$', 'refresh_lock'),
    )

urlpatterns += patterns('',
        (r'jsi18n/$', 'django.views.i18n.javascript_catalog', {'packages': 'locking'}),
    )