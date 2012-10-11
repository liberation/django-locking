# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import simplejson

from django.conf import settings
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.template.base import Template
from django.test.client import Client
from django.contrib.auth.models import User

from locking import time_until_expiration, models

from utils import TestCase
from models import Story, Unlockable


class BaseTestCase(TestCase):
    def setUp(self):
        self.alt_story = Story.objects.create(
            content="This is a little lockable story by a sad robot.",
        )
        self.story = Story.objects.create(
            content="This is another article ready for locking and unlocking.",
        )
        self.unlockable = Unlockable.objects.create(
            content="This is an object that doesn't have LockableModel as a base class."
        )
        self.user = User.objects.create_superuser("Stan", "stan@example.com", "secret")
        self.alt_user = User.objects.create_user("Fred", "fred@example.com", "secret")


class AppTestCase(BaseTestCase):
    def FIXME_test_hard_lock(self):
        # you can save a hard lock once (to initiate the lock)
        # but after that saving without first unlocking raises an error
        self.story.lock_for(self.user, hard_lock=True)
        self.assertEquals(self.story.lock_type, "hard")
        self.story.save()
        self.assertRaises(models.ObjectLockedError, self.story.save)

    def test_soft_lock(self):
        self.story.lock_for(self.user)
        self.story.save()
        self.assertEquals(self.story.lock_type, "soft")
        self.story.save()

    def test_lock_for(self):
        self.story.lock_for(self.user)
        self.assertTrue(self.story.is_locked)
        self.story.save()
        self.assertTrue(self.story.is_locked)

    def test_lock_for_overwrite(self):
        # we shouldn't be able to overwrite an active lock by another user
        self.story.lock_for(self.alt_user)
        self.assertRaises(models.ObjectLockedError, self.story.lock_for, self.user)

    def test_unlock(self):
        self.story.lock_for(self.user)
        self.story.unlock()
        self.assertFalse(self.story.is_locked)

    def test_hard_unlock(self):
        self.story.lock_for(self.user, hard_lock=True)
        self.story.unlock_for(self.user)
        self.assertFalse(self.story.is_locked)
        self.story.unlock()

    def test_unlock_for_self(self):
        self.story.lock_for(self.user)
        self.story.unlock_for(self.user)
        self.assertFalse(self.story.is_locked)

    def test_unlock_for_disallowed(self, hard_lock=False):
        # we shouldn't be able to disengage a lock that was put in place by another user
        self.story.lock_for(self.alt_user, hard_lock=hard_lock)
        self.assertRaises(models.ObjectLockedError, self.story.unlock_for, self.user)

    def FIXME_test_hard_unlock_for_disallowed(self):
        self.test_unlock_for_disallowed(hard_lock=True)

    def test_lock_expiration(self):
        self.story.lock_for(self.user)
        self.assertTrue(self.story.is_locked)
        self.story.locked_at = datetime.now() - timedelta(seconds=time_until_expiration + 1)
        self.assertFalse(self.story.is_locked)

    def test_lock_applies_to(self):
        self.story.lock_for(self.alt_user)
        applies = self.story.lock_applies_to(self.user)
        self.assertTrue(applies)

    def test_lock_doesnt_apply_to(self):
        self.story.lock_for(self.user)
        applies = self.story.lock_applies_to(self.user)
        self.assertFalse(applies)

    def test_is_locked_by(self):
        self.story.lock_for(self.user)
        self.assertEquals(self.story.locked_by, self.user)

    def test_is_unlocked(self):
        # this might seem like a silly test, but an object
        # should be unlocked unless it has actually been locked
        self.assertFalse(self.story.is_locked)

    def FIXME_test_locking_bit_when_locking(self):  # _state is not used anymore since we do atomic save through "update" method
        # when we've locked something, we should set an administrative
        # bit so other developers can know a save will do a lock or
        # unlock and respond to that information if they so wish.
        self.story.content = "Blah"
        self.assertEquals(self.story._state.locking, False)
        self.story.lock_for(self.user)
        self.assertEquals(self.story._state.locking, True)
        self.story.save()
        self.assertEquals(self.story._state.locking, False)

    def FIXME_test_locking_bit_when_unlocking(self):  # _state is not used anymore since we do atomic save through "update" method
        # when we've locked something, we should set an administrative
        # bit so other developers can know a save will do a lock or
        # unlock and respond to that information if they so wish.
        self.story.content = "Blah"
        self.assertEquals(self.story._state.locking, False)
        self.story.lock_for(self.user)
        self.story.unlock_for(self.user)
        self.assertEquals(self.story._state.locking, True)
        self.story.save()
        self.assertEquals(self.story._state.locking, False)



class BrowserTestCase(BaseTestCase):
    apps = ('locking.tests', 'django.contrib.auth', 'django.contrib.admin', )
    users = [
        {"username": "Stan", "password": "secret"},  # Stan is a superuser
        {"username": "Fred", "password": "secret"},  # Fred has pretty much no permissions whatsoever
        ]
    # REFACTOR:
    #urls = 'locking.tests.urls'

    def setUp(self):
        super(BrowserTestCase, self).setUp()
        # some objects we might use directly, instead of via the client
        user_objs = User.objects.all()
        self.user, self.alt_user = user_objs
        # client setup
        self.client = Client()
        self.client.login(**self.users[0])
        # refactor: http://docs.djangoproject.com/en/dev/topics/testing/#urlconf-configuration
        # is probably a smarter way to go about this
        self.urls = {
            "change": reverse('admin:tests_story_change', args=[self.story.pk]),
            "changelist": reverse('admin:tests_story_changelist'),
        }

    def tearDown(self):
        pass

    # Some terminology:
    # - 'disallowed' is when the locking system does not allow a certain operation
    # - 'unauthorized' is when Django does not permit a user to do something
    # - 'unauthenticated' is when a user is logged out of Django

    def test_lock_when_allowed(self):
        response = self.client.get(self.urls['change'])
        self.assertEquals(response.status_code, 200)
        self.assertTrue(self.story.is_locked)

    def test_lock_when_logged_out(self):
        self.client.logout()
        self.client.get(self.urls['change'])  # redirect to login page
        self.assertFalse(self.story.is_locked)

    def test_lock_when_unauthorized(self):
        # when a user doesn't have permission to change the model
        # this tests the user_may_change_model decorator
        self.client.logout()
        self.client.login(**self.users[1])
        self.client.get(self.urls['change'])  # redirect to login page
        self.assertFalse(self.story.is_locked)

    def test_lock_when_does_not_apply(self):
        # Ensure a model wich do not inherit LockableModel, is not lockable
        self.client.get(reverse('admin:tests_unlockable_change', args=[self.unlockable.pk]))
        self.assertFalse(hasattr(self.unlockable, 'is_locked'))

    def test_lock_when_already_locked(self):
        self.story.lock_for(self.alt_user)
        self.story.save()
        response = self.client.get(reverse('admin:refresh_lock_tests_story', args=[self.story.pk]))
        self.assertEquals(response.status_code, 409)

    def test_unlock_when_allowed(self):
        self.story.lock_for(self.user)
        self.story.save()
        response = self.client.get(reverse('admin:unlock_tests_story', args=[self.story.pk]))
        self.assertEquals(response.status_code, 200)
        story = Story.objects.get(pk=self.story.id)
        self.assertFalse(story.is_locked)

    def test_unlock_when_disallowed(self):
        self.story.lock_for(self.alt_user)
        self.story.save()
        response = self.client.get(reverse('admin:unlock_tests_story', args=[self.story.pk]))
        self.assertEquals(response.status_code, 403)

    def test_refresh_lock(self):
        self.story.lock_for(self.user)
        self.story.save()
        response = self.client.get(reverse('admin:refresh_lock_tests_story', args=[self.story.pk]))
        data = simplejson.loads(response.content)
        self.assertTrue('original_locked_at' in data.keys())
        self.assertTrue('original_modified_at' in data.keys())

    def test_js_variables_tag(self):
        rendered = Template("{% load locking_tags %}{% locking_variables %}").render(RequestContext(None))
        self.assertTrue('"time_until_warning": %d' % settings.LOCKING['time_until_warning'] in rendered)
        self.assertTrue('"time_until_expiration": %d' % settings.LOCKING['time_until_expiration'] in rendered)

    def test_admin_media(self):
        response = self.client.get(self.urls['change'])
        self.assertContains(response, 'admin.locking.js')

    def test_admin_changelist_when_locked(self):
        self.story.lock_for(self.alt_user)
        self.story.save()
        response = self.client.get(self.urls['changelist'])
        self.assertContains(response, 'locking/img/lock.png')

    def test_admin_changelist_when_locked_self(self):
        self.test_lock_when_allowed()
        response = self.client.get(self.urls['changelist'])
        self.assertContains(response, 'locking/img/page_edit.png')

    def test_admin_changelist_when_unlocked(self):
        response = self.client.get(self.urls['changelist'])
        self.assertNotContains(response, 'locking/img')
