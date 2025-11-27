import time
import statistics

import pytest
import psutil

from dispatcherd.factories import get_control_from_settings

from django.test import override_settings
from django.utils.timezone import now

from awx.api.versioning import reverse

from awx.main.models import Job, JobTemplate, WorkflowJob

from awx.main.tests.live.tests.conftest import wait_for_job, wait_to_leave_status

N = 100

N_series = [1, 5, 10, 20, 30, 45, 50, 75, 100, 150, 200]
# N_series = [10]


def find_dispatcher_pid():
    return get_control_from_settings().control_with_reply('status')[0]['main']['pid']


def sample_process_tree_rss(root_pid: int) -> int:
    """
    Returns total RSS (bytes) for root process + all its descendants.

    This is usually what you want for "background task service memory".
    """
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return 0

    procs = [root]
    try:
        procs += root.children(recursive=True)
    except psutil.NoSuchProcess:
        pass

    rss_total = 0
    for p in procs:
        try:
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                rss_total += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rss_total


@pytest.fixture
def perf_jt(demo_inv, project_factory, live_tmp_folder, admin):
    jt = JobTemplate.objects.filter(name='test_many_fast_launch').first()
    if jt:
        jt.delete()
        jt = None

    proj = project_factory(scm_url=f'file://{live_tmp_folder}/debug')

    if proj.current_job:
        wait_for_job(proj.current_job)
    assert proj.get_project_path()
    assert 'debug.yml' in proj.playbooks

    jt_data = {'project': proj, 'playbook': 'debug.yml', 'inventory': demo_inv, 'allow_simultaneous': True, 'created_by': admin, 'modified_by': admin}

    jt, created = JobTemplate.objects.get_or_create(name='test_many_fast_launch', defaults=jt_data)
    return jt


def test_many_fast_launch(perf_jt):
    jobs = []
    for i in range(N):
        print(f'creating {i}')
        job = perf_jt.create_unified_job()
        jobs.append(job)

    for i, job in enumerate(jobs):
        print(f'signl_start {i}')
        job.signal_start()

    start_times = []
    run_times = []
    for job in jobs:
        wait_for_job(job)
        assert job.status == 'successful'
        start_times += [(job.started - job.created).total_seconds()]
        run_times += [(job.finished - job.started).total_seconds()]

    print('times taken to start')
    print(' '.join([str(t) for t in start_times]))
    print('')
    print('times taken to run')
    print(' '.join([str(t) for t in run_times]))

    raise Exception({'start_mean': statistics.mean(start_times), 'run_mean': statistics.mean(run_times)})


@pytest.fixture
def bulk_launcher(post, admin, perf_jt):
    def _rf(num: int) -> WorkflowJob:
        with override_settings(BULK_JOB_MAX_LAUNCH=num + 1):
            jobs = [{'unified_job_template': perf_jt.id} for _ in range(num)]
            response = post(url=reverse('api:bulk_job_launch'), data={'name': 'Bulk Job Launch', 'jobs': jobs}, user=admin, expect=201)
            data = response.data
            wj_id = data['id']
            wj = WorkflowJob.objects.get(id=wj_id)
            return wj

    return _rf


def test_workflow_bulk_launch(bulk_launcher):
    print('N      time')
    for N_local in N_series:
        wj = bulk_launcher(N_local)
        wait_for_job(wj)
        delta = (wj.finished - wj.created).total_seconds()
        print(f'{N_local}    {delta}')
    raise Exception('alan!')


def test_workflow_memory_use(bulk_launcher):
    print('N      time')
    mems = []
    start_times = []
    for N_local in N_series:
        start_time = time.monotonic()
        start_tz = now()
        wj = bulk_launcher(N_local)

        wait_to_leave_status(wj, 'pending')

        wait_time = 120

        # wait until all the jobs are in the running status
        for i in range(wait_time):
            time.sleep(1)
            running_ct = Job.objects.filter(status__in=['running', 'successful'], unified_job_node__workflow_job=wj.id).count()
            if running_ct == N_local:
                break
        else:
            total_ct = Job.objects.filter(unified_job_node__workflow_job=wj.id).count()
            raise RuntimeError(f'Jobs from {wj.id} never hit running status in {wait_time}s, running {running_ct}, of {total_ct}, expected {N_local}')

        # # Get the memory use and print it, everything is in running status
        pid = find_dispatcher_pid()
        # # pid = 28341
        mem = sample_process_tree_rss(pid)
        mems.append(mem)

        # Record start time metrics
        delta = time.monotonic() - start_time
        start_times.append(delta)
        if delta > 20:
            last_job = Job.objects.filter(unified_job_node__workflow_job=wj.id).order_by('-started').first()
            print(f'Job with latest starting time: {last_job.id}')
            print(last_job.celery_task_id)
            for fd_name in ('created', 'started', 'finished'):
                val = getattr(last_job, fd_name)
                if val is None:
                    continue
                rel_t = (val - start_tz).total_seconds()
                print(f'{fd_name}    {rel_t}')

        # Clean up after ourselves
        wj.cancel()
        time.sleep(2)

    print('')
    print('N      memory      start_time    long_job')
    for N, mem, st in zip(N_series, mems, start_times):
        print(f'{N}   {mem}    {st}')

    raise Exception('alan!')
