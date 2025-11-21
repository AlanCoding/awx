import time
import statistics

from awx.main.models import Job, JobTemplate

from awx.main.tests.live.tests.conftest import wait_for_job

N = 1000


def test_many_fast_launch(demo_inv, project_factory, live_tmp_folder, admin):
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

    jobs = []
    for i in range(N):
        job = jt.create_unified_job()
        job.signal_start()
        jobs.append(job)

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
