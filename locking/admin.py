# coding=utf8
import simplejson
from datetime import datetime
from django.conf.urls.defaults import patterns, url
from django.contrib import admin
from django.conf import settings
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib.admin.util import unquote, model_ngettext
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import formats

from locking.models import ObjectLockedError

class LockableAdmin(admin.ModelAdmin):
    class Media():
        css = {
               'all': ('locking/css/locking.css',)
            }
        js = (
              'locking/js/admin.locking.js',
              'locking/js/jquery.url.packed.js',
             )

    def force_unlock(self, request, queryset):
        """
        Admin action to force unlocking all objects in `queryset`.

        Intended for superusers.
        """
        if not self.has_change_permission(request):
            raise PermissionDenied

        for obj in queryset:
            obj.unlock()

        n = queryset.count()

        if n:
            self.message_user(request, _("Successfully unlocked %(count)d %(items)s.") % {
                "count": n, "items": model_ngettext(self.opts, n)
            })

    force_unlock.short_description = ugettext_lazy("Force unlocking selected %(verbose_name_plural)s")

    def unlock_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        # Users who don't have exclusive access to an object anymore may still
        # request we unlock an object. This happens e.g. when a user navigates
        # away from an edit screen that's been open for very long.
        # When this happens, LockableModel.unlock_for will throw an exception, 
        # and we just ignore the request.
        # That way, any new lock that may since have been put in place by another 
        # user won't get accidentally overwritten.
        try:
            obj.unlock_for(request.user)
            obj._is_a_locking_request = True
            return HttpResponse(status=200)
        except ObjectLockedError:
            return HttpResponse(status=403)

    def refresh_lock_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        try:
            obj.lock_for(request.user)
        except ObjectLockedError:
            # The user tried to overwrite an existing lock by another user.
            # No can do, pal!
            return HttpResponse(status=409)  # Conflict
    
        # Format date like a DateTimeInput would have done
        format = formats.get_format('DATETIME_INPUT_FORMATS')[0]
        original_locked_at = obj.locked_at.strftime(format)
        original_modified_at = obj.modified_at.strftime(format)
    
        response = simplejson.dumps({
            'original_locked_at': original_locked_at,
            'original_modified_at': original_modified_at,
        })
    
        return HttpResponse(response, mimetype="application/json")


    def get_urls(self):
        """
        Override get_urls() to add a locking URLs.
        """
        urls = super(LockableAdmin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.module_name
        locking_urls = patterns('',
            url(r'^(.+)/unlock/$',
                self.admin_site.admin_view(self.unlock_view),
                name='unlock_%s_%s' % info),
            url(r'^(.+)/refresh_lock/$',
                self.admin_site.admin_view(self.refresh_lock_view),
                name='refresh_lock_%s_%s' % info),
        )
        return locking_urls + urls
        
    def changelist_view(self, request, extra_context=None):
        # we need the request objects in a few places where it's usually not present, 
        # so we're tacking it on to the LockableAdmin class
        self.request = request
        return super(LockableAdmin, self).changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change, *args, **kwargs):
        # object creation doesn't need/have locking in place
        if not form.is_locking_disabled() and obj.pk:
            obj.unlock_for(request.user)
        super(LockableAdmin, self).save_model(request, obj, form, change, *args, 
                                          **kwargs)

    def get_object(self, request, object_id):
        obj = super(LockableAdmin, self).get_object(request, object_id)
        if obj is not None:
            obj._request_user = request.user

        return obj

    def lock(self, obj):
        if obj.is_locked:
            seconds_remaining = obj.lock_seconds_remaining
            minutes_remaining = seconds_remaining/60
            locked_until = _("Still locked for %s minutes by %s") \
                % (minutes_remaining, obj.locked_by)
            if self.request.user == obj.locked_by:
                locked_until_self = _("You have a lock on this article for %s more minutes.") \
                    % (minutes_remaining)
                return '<img src="%slocking/img/page_edit.png" title="%s" />' \
                    % (settings.MEDIA_URL, locked_until_self)
            else:
                locked_until = _("Still locked for %s minutes by %s") \
                    % (minutes_remaining, obj.locked_by)
                return '<img src="%slocking/img/lock.png" title="%s" />' \
                    % (settings.MEDIA_URL, locked_until)

        else:
            return ''
    lock.allow_tags = True
    list_display = ('__str__', 'lock')