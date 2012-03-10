# -*- coding: utf-8 -*-

from django.conf import settings
from django import template
from django.utils import simplejson as json
from django.utils.html import escape

register = template.Library()
    
@register.inclusion_tag('locking/js_variables.html', takes_context=True)
def locking_variables(context):
    """
    Export JS variables (locking settings + current page's locking infos) to
    enable locking management at the client level.
    """
    locking_infos = {}
    locking_error_when_saving = {}
    locking_settings = {
        'time_until_expiration': settings.LOCKING['time_until_expiration'],
        'time_until_warning': settings.LOCKING['time_until_warning'],
    }
    change = context.get('change', False)
    if change:
        # Export current page's locking infos to enable locking management
        # (disable form, display "is locked" message, etc.) at the client level
        original = context['original']
        request = context['request']
        is_POST_response = request.method == 'POST'
        locking_infos = {
            "is_active": original.is_locked,
            "for_user": escape(getattr(original.locked_by, 'username', '')),
            "applies": original.lock_applies_to(request.user),
            "change_form_id": "%s_form" % (original._meta.module_name,),
            "was_already_locked_by_user": getattr(original, '_was_already_locked_by_user', False),
            "is_POST_response": is_POST_response,
            "error_when_saving": None,
            "change": True
        }
        # If we are responding after a POST, export locking errors if any
        model_form  = context['adminform'].form
        if is_POST_response:
            locking_infos["error_when_saving"] = getattr(model_form, '_locking_error_when_saving', None)

    data = {
        'locking_settings': json.dumps(locking_settings),
        'locking_infos': json.dumps(locking_infos),
    }

    return data
