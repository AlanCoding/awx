#!/bin/bash
set +x

bootstrap_development.sh

# This file will be re-written when the dispatcher calls reconfigure_rsyslog(),
# but it needs to exist when supervisor initially starts rsyslog to prevent the
# container from crashing. This was the most minimal config I could get working.
cat << EOF > /var/lib/awx/rsyslog/rsyslog.conf
action(type="omfile" file="/dev/null")
EOF

cd /awx_devel
# Start the services
exec make supervisor
