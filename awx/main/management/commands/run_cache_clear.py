import logging

from django.core.management.base import BaseCommand
from django.core.cache import cache
from awx.main.dispatch import pg_bus_conn
from awx.conf import settings_registry

logger = logging.getLogger('awx.main.cache_clear')


class Command(BaseCommand):
    """
    Cache Clear
    Runs as a management command and starts a daemon that listens for a pg_notify message to clear the cache.
    """

    help = 'Launch the cache clear daemon'

    def handle(self, *arg, **options):
        try:
            with pg_bus_conn(new_connection=True) as conn:
                conn.listen("tower_settings_change")
                for e in conn.events(yield_timeouts=True):
                    if e is not None:
                        logger.warning(f"Cache clear request received. Clearing now, paylod: {e.payload}")
        except Exception:
            # Log unanticipated exception in addition to writing to stderr to get timestamps and other metadata
            logger.exception('Encountered unhandled error in cache clear main loop')
            raise
