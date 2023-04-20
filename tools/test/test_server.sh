#!/bin/bash
set +x

cd /awx_devel

make awx-link

awx-manage migrate --noinput -v0

awx-manage createsuperuser --noinput --username=admin --email=admin@localhost

exec $@
