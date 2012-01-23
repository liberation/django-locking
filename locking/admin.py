# coding=utf8
from datetime import datetime
from django.contrib import admin
from django.conf import settings
from django.utils.translation import ugettext as _

class LockableAdmin(admin.ModelAdmin):
    class Media():
        css = {
               'all': ('locking/css/locking.css',)
            }
        js = (
              'locking/js/admin.locking.js',
              'locking/js/jquery.url.packed.js',
             )
        
    def changelist_view(self, request, extra_context=None):
        # we need the request objects in a few places where it's usually not present, 
        # so we're tacking it on to the LockableAdmin class
        self.request = request
        return super(LockableAdmin, self).changelist_view(request, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        If we are in change view, try to lock ``obj``.
        """
        if change:
            if not obj.lock_applies_to(request.user):
                # obj is not locked or has been locked by current user
                obj.lock_for(request.user)
                obj.save()  # FIXME Use update!
                
        return super(LockableAdmin, self).render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def save_model(self, request, obj, form, change, *args, **kwargs):
        # object creation doesn't need/have locking in place
        if obj.pk:
            obj.unlock_for(request.user)
        super(LockableAdmin, self).save_model(request, obj, form, change, *args, 
                                          **kwargs)

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