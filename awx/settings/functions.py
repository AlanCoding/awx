import os
from typing import Any
from dynaconf import Dynaconf
from dynaconf.utils.functional import empty
from .application_name import get_application_name


def toggle_feature_flags(settings: Dynaconf) -> dict[str, Any]:
    """Toggle FLAGS based on installer settings.
    FLAGS is a django-flags formatted dictionary.
        FLAGS={
            "FEATURE_SOME_PLATFORM_FLAG_ENABLED": [
                {"condition": "boolean", "value": False, "required": True},
                {"condition": "before date", "value": "2022-06-01T12:00Z"},
            ]
        }
    Installers will place `FEATURE_SOME_PLATFORM_FLAG_ENABLED=True/False` in the settings file.
    This function will update the value in the index 0 in FLAGS with the installer value.
    """
    data = {}
    for feature_name, feature_content in settings.get("FLAGS", {}).items():
        if (installer_value := settings.get(feature_name, empty)) is not empty:
            feature_content[0]["value"] = installer_value
            data[f"FLAGS__{feature_name}"] = feature_content
    return data


def merge_application_name(settings):
    """Return a dynaconf merge dict to set the application name for the connection."""
    data = {}
    if "sqlite3" not in settings.get("DATABASES__default__ENGINE", ""):
        data["DATABASES__default__OPTIONS__application_name"] = get_application_name(settings.get("CLUSTER_HOST_ID"))
    return data


def add_backwards_compatibility():
    """Add backwards compatibility for AWX_MODE.

    Before dynaconf integration the usage of AWX settings was supported to be just
    DJANGO_SETTINGS_MODULE=awx.settings.production or DJANGO_SETTINGS_MODULE=awx.settings.development
    (development_quiet and development_kube were also supported).

    With dynaconf the DJANGO_SETTINGS_MODULE should be set always to "awx.settings" as the only entry point
    for settings  and then "AWX_MODE" can be set to any of production,development,quiet,kube
    or a combination of them separated by comma.

    E.g:

        export DJANGO_SETTINGS_MODULE=awx.settings
        export AWX_MODE=production
        awx-manage [command]
        dynaconf [command]

    If pointing `DJANGO_SETTINGS_MODULE` to `awx.settings.production` or `awx.settings.development` then
    this function will set `AWX_MODE` to the correct value.
    """
    django_settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "awx.settings")
    if django_settings_module == "awx.settings":
        return

    current_mode = os.getenv("AWX_MODE", "")
    for _module_name in ["development", "production", "development_quiet", "development_kube"]:
        if django_settings_module == f"awx.settings.{_module_name}":
            _mode = current_mode.split(",")
            if "development_" in _module_name and "development" not in current_mode:
                _mode.append("development")
            _mode_fragment = _module_name.replace("development_", "")
            if _mode_fragment not in _mode:
                _mode.append(_mode_fragment)
            os.environ["AWX_MODE"] = ",".join(_mode)
