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
