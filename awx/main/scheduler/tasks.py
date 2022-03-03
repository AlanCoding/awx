# Python
import logging

# AWX
from awx.main.scheduler import TaskManager
from awx.main.dispatch.publish import task
from awx.main.dispatch import get_local_queuename

logger = logging.getLogger('awx.main.scheduler')


@task(queue=get_local_queuename, timeout=60 * 5)
def run_task_manager():
    logger.debug("Running task manager.")
    TaskManager().schedule()
