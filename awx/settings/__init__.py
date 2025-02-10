# Copyright (c) 2015 Ansible, Inc.
# All Rights Reserved.
import os
from ansible_base.lib.dynamic_config import (
    factory,
    export,
    load_envvars,
    load_standard_settings_files,
    validate,
)
from .application_name import merge_application_name

# Create a the standard DYNACONF instance which will come with DAB defaults
# This loads defaults.py and environment specific file e.g: development_defaults.py
DYNACONF = factory(
    __name__,
    "AWX",
    environments=("development", "production", "quiet", "kube"),
    settings_files=["defaults.py"],
)

# Store snapshot before loading any custom config file
DEFAULTS_SNAPSHOT = {}
if DYNACONF.is_development_mode:
    DYNACONF.set(
        "DEFAULTS_SNAPSHOT",
        DYNACONF.as_dict(internal=False),  # should use deepcopy here?
        loader_identifier="awx.settings:DEFAULTS_SNAPSHOT",
    )
##########################################################################################
#  Any settings loaded after this point will be marked as as a read_only database setting
##########################################################################################

# Load extra config from the now deprecated /etc/tower/ directory
# This is only for backwards compatibility and will be removed in the future
# Load settings from any .py files in the global conf.d directory specified in
# the environment, defaulting to /etc/tower/conf.d/.
# Load remaining settings from the global settings file specified in the
# environment, defaulting to /etc/tower/settings.py.
# Attempt to load settings from /etc/tower/settings.py first, followed by
# /etc/tower/conf.d/*.py.
settings_dir = os.environ.get('AWX_SETTINGS_DIR', '/etc/tower/conf.d/')
settings_files_path = os.path.join(settings_dir, '*.py')
settings_file_path = os.environ.get('AWX_SETTINGS_FILE', '/etc/tower/settings.py')
DYNACONF.load_file(settings_file_path)
DYNACONF.load_file(settings_files_path)

# Load new standard settings files from
#  /etc/ansible-automation-platform/ and /etc/ansible-automation-platform/awx/
# this is to allow for a smoother transition from legacy (above) to new settings standard paths
load_standard_settings_files(DYNACONF)

# Load optional development only settings
if DYNACONF.get_environ("AWX_KUBE_DEVEL"):
    DYNACONF.load_file("kube_defaults.py")
else:
    DYNACONF.load_file("local_*.py")

# Check at least one required setting file has been loaded
if "production" in DYNACONF.current_env.lower():
    required_settings_paths = [
        os.path.dirname(settings_file_path),
        "/etc/ansible-automation-platform/",
    ]
    # check if at least one file has been loaded any of the required paths
    # use DYNACONF._loaded_files to check any filename inside the paths
    # if not loaded then raise an ImproperlyConfigured error
    for path in required_settings_paths:
        if any(path in f for f in DYNACONF._loaded_files):
            break
    else:
        from django.core.exceptions import ImproperlyConfigured

        msg = 'No AWX configuration found at %s.' % required_settings_paths
        msg += '\nDefine the AWX_SETTINGS_FILE environment variable to '
        msg += 'specify an alternate path.'
        raise ImproperlyConfigured(msg)

# Load envvars at the end to allow them to override everything loaded so far
load_envvars(DYNACONF)

# This must run after all custom settings are imported
DYNACONF.update(
    merge_application_name(DYNACONF),
    loader_identifier="awx.settings:merge_application_name",
    merge=True,
)

# Update django.conf.settings with DYNACONF keys.
export(__name__, DYNACONF)

# Validate the settings according to the validators registered
validate(DYNACONF)
