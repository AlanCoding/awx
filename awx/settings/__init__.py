# Copyright (c) 2015 Ansible, Inc.
# All Rights Reserved.
from ansible_base.lib.dynamic_config import factory, export, load_standard_settings_files
from .application_name import merge_application_name
from dynaconf import Validator
from dynaconf.loaders import env_loader


DYNACONF = factory(
    "AWX",
    environments=("development", "production", "quiet", "kube"),
    settings_files=["defaults.py"],
)
DYNACONF.validators.register(Validator("FOO", required=True, gt=99))

# Store snapshot before loading any custom config file
DEFAULTS_SNAPSHOT = {}
if DYNACONF.is_development_mode:
    DYNACONF.set(
        "DEFAULTS_SNAPSHOT",
        DYNACONF.as_dict(internal=False),  # should use deepcopy here?
        loader_identifier="awx.settings:DEFAULTS_SNAPSHOT",
    )
###############################################################################################
#
#  Any settings loaded after this point will be marked as as a read_only database setting
#
################################################################################################

# Load extra config
DYNACONF.load_file("/etc/tower/settings.py")
DYNACONF.load_file("/etc/tower/conf.d/*.py")
if DYNACONF.get_environ("AWX_KUBE_DEVEL"):
    DYNACONF.load_file("kube_defaults.py")
else:
    DYNACONF.load_file("local_*.py")

# Load new standard settings files from /etc/ansible-automation-platform/config/awx/
load_standard_settings_files(DYNACONF)

# Load envvars at the end to allow them to override everything
env_loader.load(DYNACONF, identifier="awx.settings")

# This must run after all custom settings are imported
DYNACONF.update(
    merge_application_name(DYNACONF),
    loader_identifier="awx.settings:merge_application_name",
    merge=True,
)

# Update django.conf.settings with DYNACONF keys.
export(DYNACONF)

# Validate the settings according to the validators registered
DYNACONF.validators.validate()
