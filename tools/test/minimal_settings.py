# Remove annoying things that require pre-loaded data which we do not want anyway
MIDDLEWARE.remove('awx.main.middleware.MigrationRanCheckMiddleware')  # NOQA
INSTALLED_APPS.remove('django.contrib.sites')  # NOQA


# Monkey patch the migration command to our hack that migrates straight to current schema
from django.core.management.commands import migrate


# For background on where this method comes from, see Django testing setup
# https://github.com/django/django/blob/c813fb327cb1b09542be89c5ceed367826236bc2/django/db/backends/base/creation.py#L32
class MigrateToCurrent(migrate.Command):
    help = 'Hacked migration - creates tables to match current models'

    def handle(self, *args, **options):
        from django.apps import apps
        from django.conf import settings

        settings.MIGRATION_MODULES = {app.label: None for app in apps.get_app_configs()}
        options['run_syncdb'] = True
        super().handle(*args, **options)

        from awx.main.models.credential import CredentialType

        CredentialType.setup_tower_managed_defaults(apps)


migrate.Command = MigrateToCurrent

# Get rid of redis cache, do not need it for minimal deploy
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Allow for database reuse
SECRET_KEY = "pGT9A9U59ajcxkVlmUiVZPK6JcgX+M6VjVru5nPY0ws="
