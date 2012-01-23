# -*- coding: utf-8 -*-

from django.conf import settings
from django import template
from django.utils import simplejson as json

register = template.Library()
    
@register.inclusion_tag('locking/js_variables.html', takes_context=True)
def locking_variables(context):
    """
    Export JS variables (locking settings + current page's locking infos) to
    enable locking management at the client level.
    """
    locking_infos = {}
    locking_settings = {
        'base_url': '/ajax/admin',  # FIXME don't harcode base URL !
        'time_until_expiration': settings.LOCKING['time_until_expiration'],
        'time_until_warning': settings.LOCKING['time_until_warning'],
    }
    change = context.get('change', False)
    if change:
        # Export current page's locking infos to enable locking management
        # (disable form, display "is locked" message, etc.) at the client level
        original = context['original']
        request = context['request']
        locking_infos = {
            "is_active": original.is_locked,
            "for_user": getattr(original.locked_by, 'username', None),
            "applies": original.lock_applies_to(request.user),
            "change_form_id": "%s_form" % (original._meta.module_name,)
        }

    data = {
        'locking_settings': json.dumps(locking_settings),
        'locking_infos': json.dumps(locking_infos),
    }

    return data
