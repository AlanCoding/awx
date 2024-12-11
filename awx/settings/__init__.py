# Copyright (c) 2015 Ansible, Inc.
# All Rights Reserved.
from ansible_base.lib.dynamic_config import factory, export
from .application_name import get_application_name
from dynaconf import Validator


def set_application_name(settings):
    data = {"dynaconf_merge": True}
    if settings.get("DATABASES") and settings.DATABASES.get("default"):
        if "sqlite3" not in settings.DATABASES.default.ENGINE:
            data["DATABASES__default__OPTIONS__application_name"] = get_application_name(settings.CLUSTER_HOST_ID)
    return data


DYNACONF = factory(
    "AWX",
    environments=("development", "production", "quiet", "kube"),
    settings_files=["defaults.py"],
)
DYNACONF.validators.register(Validator("FOO", required=True))

# Store snapshot before loading any custom config file
if DYNACONF.current_env == "development":
    DYNACONF.set("DEFAULTS_SNAPSHOT", DYNACONF.as_dict(internal=False))

# Load extra config
DYNACONF.load_file("/etc/tower/settings.py")
DYNACONF.load_file("/etc/tower/conf.d/*.py")
if DYNACONF.get_environ("AWX_KUBE_DEVEL"):
    DYNACONF.load_file("kube_defaults.py")
else:
    DYNACONF.load_file("local_*.py")

# This must run after all custom settings are imported
DYNACONF.update(set_application_name(DYNACONF))

# Update django.conf.settings with DYNACONF keys.
export(DYNACONF)

# Validate the settings according to the validators registered
DYNACONF.validators.validate()
