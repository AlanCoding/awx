from django.conf import LazySettings

from rest_framework.fields import empty


class ConfLazySettings(LazySettings):
    def __getattr__(self, name):
        # Django 1.10 added an optimization to settings lookup:
        # https://code.djangoproject.com/ticket/27625
        # https://github.com/django/django/commit/c1b221a9b913315998a1bcec2f29a9361a74d1ac
        # This change caches settings lookups on the __dict__ of the LazySettings
        # object, which is not okay to do in an environment where settings can
        # change in-process (the entire point of awx's custom settings implementation)
        # This restores the original behavior that *does not* cache.
        if self._wrapped is empty:
            self._setup(name)
        return getattr(self._wrapped, name)


settings = LazySettings()
