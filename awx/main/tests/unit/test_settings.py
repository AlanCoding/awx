from django.conf import settings
from awx.settings import REST_FRAMEWORK
from awx.settings.functions import toggle_feature_flags, merge_application_name

LOCAL_SETTINGS = (
    'ALLOWED_HOSTS',
    'BROADCAST_WEBSOCKET_PORT',
    'BROADCAST_WEBSOCKET_VERIFY_CERT',
    'BROADCAST_WEBSOCKET_PROTOCOL',
    'BROADCAST_WEBSOCKET_SECRET',
    'DATABASES',
    'CACHES',
    'DEBUG',
    'NAMED_URL_GRAPH',
    'DISPATCHER_MOCK_PUBLISH',
)


def test_postprocess_auth_basic_enabled():
    """The final loaded settings should have basic auth enabled."""
    assert 'awx.api.authentication.LoggedBasicAuthentication' in REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']


def test_default_settings():
    """Ensure that all default settings are present in the snapshot."""
    for k in dir(settings):
        if k not in settings.DEFAULTS_SNAPSHOT or k in LOCAL_SETTINGS:
            continue
        default_val = getattr(settings.default_settings, k, None)
        snapshot_val = settings.DEFAULTS_SNAPSHOT[k]
        assert default_val == snapshot_val, f'Setting for {k} does not match shapshot:\nsnapshot: {snapshot_val}\ndefault: {default_val}'


def test_django_conf_settings_is_awx_settings():
    """Ensure that the settings loaded from dynaconf are the same as the settings delivered to django."""
    assert settings.REST_FRAMEWORK is REST_FRAMEWORK


def test_dynaconf_is_awx_settings():
    """Ensure that the settings loaded from dynaconf are the same as the settings delivered to django."""
    assert settings.DYNACONF.REST_FRAMEWORK is REST_FRAMEWORK


def test_production_settings_can_be_directly_imported():
    """Ensure that the production settings can be directly imported."""
    from awx.settings.production import REST_FRAMEWORK
    from awx.settings.production import DEBUG

    assert settings.REST_FRAMEWORK is REST_FRAMEWORK
    assert DEBUG is False


def test_development_settings_can_be_directly_imported():
    """Ensure that the development settings can be directly imported."""
    from awx.settings.development import REST_FRAMEWORK
    from awx.settings.development import DEBUG  # actually set on defaults.py and not overridden in development.py

    assert settings.REST_FRAMEWORK is REST_FRAMEWORK
    assert DEBUG is True


def test_toggle_feature_flags():
    """Ensure that the toggle_feature_flags function works as expected."""
    settings = {
        "FLAGS": {
            "FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
                {"condition": "boolean", "value": False, "required": True},
                {"condition": "before date", "value": "2022-06-01T12:00Z"},
            ]
        },
        "FEATURE_SOME_PLATFORM_FLAG_ENABLED": True,
    }
    assert toggle_feature_flags(settings) == {
        "FLAGS__FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
            {"condition": "boolean", "value": True, "required": True},
            {"condition": "before date", "value": "2022-06-01T12:00Z"},
        ]
    }


def test_merge_application_name():
    """Ensure that the merge_application_name function works as expected."""
    settings = {
        "DATABASES__default__ENGINE": "django.db.backends.postgresql",
        "CLUSTER_HOST_ID": "test-cluster-host-id",
    }
    assert merge_application_name(settings) == {"DATABASES__default__OPTIONS__application_name": "test-cluster-host-id"}
