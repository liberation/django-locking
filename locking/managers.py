import datetime
from django.db.models import Q, Manager
from django.conf import settings

def point_of_timeout():
    delta = datetime.timedelta(seconds=settings.LOCKING['time_until_expiration'])
    return datetime.datetime.now() - delta

class LockedManager(Manager):
    def get_query_set(self):
        timeout = point_of_timeout()
        return super(LockedManager, self).get_query_set().filter(locked_at__gt=timeout, locked_at__isnull=False)

class UnlockedManager(Manager):
    def get_query_set(self):
        timeout = point_of_timeout()
        return super(UnlockedManager, self).get_query_set().filter(Q(locked_at__lte=timeout) | Q(locked_at__isnull=True))