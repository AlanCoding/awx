from django.core.management.commands import migrate


# Remove annoying things that require pre-loaded data which we do not want anyway
MIDDLEWARE.remove('awx.main.middleware.MigrationRanCheckMiddleware')  # NOQA
INSTALLED_APPS.remove('django.contrib.sites')  # NOQA


# Monkey patch the migration command to our hack that migrates straight to current schema
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

        # Preload certain data here which can be used by tests
        from django.contrib.auth import get_user_model
        from awx.main.models.credential import CredentialType

        User = get_user_model()

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@localhost', 'password')
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

# Make sure that we do not run Django debug toolbar by accident
INTERNAL_IPS = ()
