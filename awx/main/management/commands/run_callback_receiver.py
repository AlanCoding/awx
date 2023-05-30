# Copyright (c) 2015 Ansible, Inc.
# All Rights Reserved.

import logging

from django.core.management.base import BaseCommand

from awx.main.dispatch import get_task_queuename
from awx.main.dispatch.control import Control
from awx.main.dispatch.pool import AutoscalePool
from awx.main.dispatch.worker import TaskWorker
from awx.main.dispatch.worker.callback import AWXJobMonitorPG


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Save Job Callback receiver
    Runs as a management command, starts jobs, and processes output.
    """

    help = 'Launch the job monitor service (formerlly the callback_receiver)'

    def add_arguments(self, parser):
        parser.add_argument('--status', dest='status', action='store_true', help='print the internal state of any running dispatchers')

    def handle(self, *arg, **options):
        if options.get('status'):
            print(Control('callback_receiver').status())
            return

        try:
            queues = [get_task_queuename() + '_job']
            consumer = AWXJobMonitorPG('dispatcher', TaskWorker(), queues, AutoscalePool(min_workers=2))
            consumer.run()
        except KeyboardInterrupt:
            logger.debug('Terminating Job Monitor')
            if consumer:
                consumer.stop()
