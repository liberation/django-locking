# encoding: utf-8

from django.contrib import admin
from locking.admin import LockableAdmin

import forms
import models


class StoryAdmin(LockableAdmin):
    form = forms.StoryAdminForm
    list_display = ('lock', 'content', )
    list_display_links = ('content', )

admin.site.register(models.Story, StoryAdmin)


class UnlockableAdmin(admin.ModelAdmin):
    pass

admin.site.register(models.Unlockable, UnlockableAdmin)
