import logging
import time


logger = logging.getLogger('awx.main.dispatch.periodic')


class Job:
    def __init__(self, name: str, data: dict):
        self.name = name
        self.data = data
        self.interval = int(data['schedule'].total_seconds())
        self.offset = 0
        self.index = 0  # number of times this job has ran
        self.missed_runs = 0  # number of times job was supposed to ran but failed to

    @property
    def next_run(self):
        """
        Gives the time until the next run with t=0 being the global_start
        of the scheduler class
        """
        return (self.index + 1) * self.interval + self.offset

    def mark_run(self, relative_time):
        new_index = int((relative_time - self.offset) / self.interval)
        if new_index > self.index + 1:
            logger.warning(f'Missed {new_index - self.index} schedules of {self.name}')
            self.missed_runs += new_index - self.index
        self.index = new_index


class Scheduler:
    def __init__(self, schedule):
        """
        Expects a schedule in the form of a dictionary like
        {
            'job1': {'schedule': timedelta(seconds=50), 'other': 'stuff'}
        }
        This can give pending jobs at a given time and time until the next job.
        Only the inverval from the values are used for scheduling,
        the rest of the data is for use by the caller to know what to run.
        """
        self.jobs = [Job(name, data) for name, data in schedule.items()]
        min_interval = min(job.interval for job in self.jobs)
        num_jobs = len(self.jobs)

        # this is intentionally oppioniated against spammy schedules
        # a core goal is to spread out the scheduled tasks (for worker management)
        # and high-frequency schedules just do not work with that
        if num_jobs > min_interval:
            raise RuntimeError(f'Number of schedules ({num_jobs}) is more than the shortest schedule interval ({min_interval} seconds).')

        # even space out jobs over the base interval
        for i, job in enumerate(self.jobs):
            job.offset = (i * min_interval) // num_jobs

        # internally times are all referenced relative to startup time, add grace period
        self.global_start = time.time() + 2.0

    def get_and_mark_pending(self):
        relative_time = time.time() - self.global_start
        to_run = []
        for job in self.jobs:
            if job.next_run <= relative_time:
                to_run.append(job)
                logger.debug(f'scheduler found {job.name} to run, {relative_time - job.next_run} seconds after target')
            job.mark_run(relative_time)
        return to_run

    def time_until_next_run(self):
        relative_time = time.time() - self.global_start
        next_job = min(self.jobs, key=lambda j: j.next_run)
        delta = next_job.next_run - relative_time
        if delta <= 0.1:
            # careful not to give 0 or negative values to the select timeout, which has unclear interpretation
            logger.warning(f'Scheduler next run of {next_job.name} is {-delta} seconds in the past')
            return 0.1
        logger.debug(f'Scheduler next run is {next_job.name} in {delta} seconds')
        return delta
