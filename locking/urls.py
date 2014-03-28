from django.conf.urls import *

urlpatterns = patterns('',
        (r'jsi18n/$', 'django.views.i18n.javascript_catalog', {'packages': 'locking'}),
    )
