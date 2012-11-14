# -*- coding: utf-8 -*-

from locking.forms import LockableForm

import models

class StoryAdminForm(LockableForm):
    class Meta:
        model = models.Story
