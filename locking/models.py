# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import models as auth
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
from django.db.models.expressions import ExpressionNode
from django.utils.translation import ugettext_lazy as _

from locking import logger
from locking import managers

class ObjectLockedError(IOError):
    pass

class Lock(models.Model):
    """
    Model containing the lock informations per object.
    """
    locked_at = models.DateTimeField(db_column=getattr(settings, "LOCKED_AT_DB_FIELD_NAME", "checked_at"), 
        null=True,
        editable=False)
    locked_by = models.ForeignKey(auth.User, 
        db_column=getattr(settings, "LOCKED_BY_DB_FIELD_NAME", "checked_by"),
        related_name="working_on_%(class)s",
        null=True,
        editable=False)
    hard_lock = models.BooleanField(db_column='hard_lock', default=False, editable=False)
    
    # Content-object field
    content_type   = models.ForeignKey(ContentType,
            verbose_name=_('content type'),
            related_name="content_type_set_for_%(class)s")
    object_id      = models.TextField(_('object ID'))
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    class Meta:
         unique_together = ('content_type', 'object_id',)


    def __unicode__(self):
        return u"Lock for %d/%s" % (self.content_type_id, self.object_id)

class LockableModelFieldsMixin(models.Model):
    """
    Mixin that adds modified_at column

    You only have to inherit from it if you don't already have the field on your
    lockable models.
    """
    class Meta:
        abstract = True

    modified_at = models.DateTimeField(
        auto_now=True,
        editable=False,
        db_column=getattr(settings, "MODIFIED_AT_DB_FIELD_NAME", "modified_at")
    )

class LockableModelMethodsMixin(models.Model):
    """
    Mixin that holds all methods of final class LockableModel.

    Inherit directly from this class (instead of LockableModel) if you want
    to declare your locking fields with custom options (on_delete, blank, etc.).
    """
    class Meta:
        abstract = True

    @property
    def lock(self):
        if not hasattr(self, '_lock'):
            ctypes = ContentType.objects.get_for_model(self)
            try:
                self._lock = Lock.objects.get(content_type=ctypes, object_id=str(self.pk))
            except Lock.DoesNotExist:
                # If there is no Lock object for this model, create it,
                # but don't save it yet (it's just here to prevent the db
                # query next time we need the lock information for this object)
                self._lock = Lock(content_type=ctypes, object_id=str(self.pk))
        return self._lock

    @lock.deleter
    def lock(self):
        del self._lock

    @property
    def locked_at(self):
        if not self.pk:
            return None
        return self.lock.locked_at

    @locked_at.setter
    def locked_at(self, value):
        self.lock.locked_at = value

    @property
    def locked_by(self):
        if not self.pk:
            return None
        return self.lock.locked_by

    @locked_by.setter
    def locked_by(self, value):
        self.lock.locked_by = value

    @property
    def hard_lock(self):
        if not self.pk:
            return False        
        return self.lock.hard_lock

    @hard_lock.setter
    def hard_lock(self, value):
        self.lock.hard_lock = value

    @property
    def lock_type(self):
        """ Returns the type of lock that is currently active. Either
        ``hard``, ``soft`` or ``None``. Read-only. """
        if self.is_locked:
            if self.hard_lock:
                return "hard"
            else:
                return "soft"
        else:
            return None

    @property
    def is_locked(self):
        """
        A read-only property that returns True or False.
        Works by calculating if the last lock (self.locked_at) has timed out or not.
        """
        if isinstance(self.locked_at, datetime):
            # We're only locked if locked_at is recent enough
            if self.locked_at > datetime.now() - timedelta(seconds=settings.LOCKING['time_until_expiration']):
                return True
            else:
                return False
        return False
    
    @property
    def lock_seconds_remaining(self):
        """
        A read-only property that returns the amount of seconds remaining before
        any existing lock times out.
        
        May or may not return a negative number if the object is currently unlocked.
        That number represents the amount of seconds since the last lock expired.
        
        If you want to extend a lock beyond its current expiry date, initiate a new
        lock using the ``lock_for`` method.
        """
        return int(settings.LOCKING['time_until_expiration'] - (datetime.now() - self.locked_at).total_seconds())
    
    def lock_for(self, user, hard_lock=False):
        """
        Together with ``unlock_for`` this is probably the most important method 
        on this model. If applicable to your use-case, you should lock for a specific 
        user; that way, we can throw an exception when another user tries to unlock
        an object they haven't locked themselves.
        
        When using soft locks (the default), any process can still use the save method
        on this object. If you set ``hard_lock=True``, trying to save an object
        without first unlocking will raise an ``ObjectLockedError``.
        
        Don't use hard locks unless you really need them. See :doc:`design`.
        """
        logger.info(u"Attempting to initiate a lock for user `%s`" % user)

        if not isinstance(user, auth.User):
            raise ValueError("You should pass a valid auth.User to lock_for.")
        
        if self.lock_applies_to(user):
            raise ObjectLockedError("This object is already locked by another user. \
                May not override, except through the `unlock` method.")
        else:
            self.lock.locked_at = datetime.now()
            self.lock.locked_by = user
            self.lock.hard_lock = hard_lock
            self.lock.save()
            logger.info(u"Initiated a %s lock for `%s` at %s" % (self.lock_type, self.locked_by, self.locked_at))     

    def unlock(self):
        """
        This method serves solely to allow the application itself or admin users
        to do manual lock overrides, even if they haven't initiated these
        locks themselves. Otherwise, use ``unlock_for``.
        """
        if self.lock.pk:
            self.lock.delete()
        del self.lock
        logger.info(u"Disengaged lock on `%s`" % self)
    
    def unlock_for(self, user):
        """
        See ``lock_for``. If the lock was initiated for a specific user, 
        unlocking will fail unless that same user requested the unlocking. 
        Manual overrides should use the ``unlock`` method instead.
        
        Will raise a ObjectLockedError exception when the current user isn't authorized to
        unlock the object.
        """
        logger.info(u"Attempting to open up a lock on `%s` by user `%s`" % (self, user))
    
        # refactor: should raise exceptions instead
        if self.is_locked_by(user):
            self.unlock()
        else:
            raise ObjectLockedError("Trying to unlock for another user than the one who initiated the currently active lock. This is not allowed. You may want to try a manual override through the `unlock` method instead.")
    
    def lock_applies_to(self, user):
        """
        A lock does not apply to the user who initiated the lock. Thus, 
        ``lock_applies_to`` is used to ascertain whether a user is allowed
        to edit a locked object.
        """
        logger.info(u"Checking if the lock on `%s` applies to user `%s`" % (self, user))
        # a lock does not apply to the person who initiated the lock
        if self.is_locked and self.locked_by != user:
            logger.info(u"Lock applies.")
            return True
        else:
            logger.info(u"Lock does not apply.")
            return False
    
    def is_locked_by(self, user):
        """
        Returns True or False. Can be used to test whether this object is locked by
        a certain user. The ``lock_applies_to`` method and the ``is_locked`` and 
        ``locked_by`` attributes are probably more useful for most intents and
        purposes.
        """
        return user == self.locked_by
    
    def save(self, *args, **kwargs):
        if self.pk and self.lock_type == 'hard':
            raise ObjectLockedError("""There is currently a hard lock in place. You may not save.
            If you're requesting this save in order to unlock this object for the user who
            initiated the lock, make sure to call `unlock_for` first, with the user as
            the argument.""")

        super(LockableModelMethodsMixin, self).save(*args, **kwargs)


class LockableModel(LockableModelFieldsMixin, LockableModelMethodsMixin):
    class Meta:
        abstract = True