import time
import statistics

import pytest

from django.test import override_settings

from awx.api.versioning import reverse

from awx.main.models import Job, JobTemplate, WorkflowJob

from awx.main.tests.live.tests.conftest import wait_for_job

N = 100

N_series = [1, 5, 10, 20, 30, 45, 50, 75, 100, 150, 200]
# N_series = [10]


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


def test_workflow_bulk_launch(perf_jt, post, admin):
    print('N      time')
    for N_local in N_series:
        with override_settings(BULK_JOB_MAX_LAUNCH=N_local + 1):
            jobs = [{'unified_job_template': perf_jt.id} for _ in range(N_local)]

            response = post(url=reverse('api:bulk_job_launch'), data={'name': 'Bulk Job Launch', 'jobs': jobs}, user=admin, expect=201)

            data = response.data
            wj_id = data['id']
            wj = WorkflowJob.objects.get(id=wj_id)
            wait_for_job(wj)
            delta = (wj.finished - wj.created).total_seconds()
            print(f'{N_local}    {delta}')
    raise Exception('alan!')
