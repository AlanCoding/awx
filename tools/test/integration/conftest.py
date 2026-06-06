import os
import time

from docker.errors import ImageNotFound
from docker import from_env
import pytest
import requests

from awxkit.api import get_registered_page
from awxkit.api.client import Connection


@pytest.fixture(scope='session')
def docker_client():
    return from_env()


@pytest.fixture(scope='session')
def base_path():
    integration_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(integration_dir, os.pardir)
    tools_dir = os.path.join(test_dir, os.pardir)
    repo_root = os.path.join(tools_dir, os.pardir)
    return os.path.abspath(repo_root)


@pytest.fixture(scope='session')
def container_factory(request, docker_client, base_path):
    """Helper method for creating an arbitrary container, integrating with pytest"""

    def run_this_container(image_name, image_options, command=None):
        name = image_options['name']
        # Pull the image if it does not exist locally
        try:
            docker_client.images.get(image_name)
        except ImageNotFound:
            docker_client.images.pull(image_name)

        # Need to run in detach mode because service needs to be persistent through tests
        image_options['detach'] = True
        args = [image_name]
        if command is not None:
            args.append(command)
        container = docker_client.containers.run(*args, **image_options)

        def kill_this_container():
            print('')
            print(f'{name} container logs:')
            print(str(container.logs(), encoding='utf-8'))
            container.stop()
            container.remove()

        request.addfinalizer(kill_this_container)
        return container

    return run_this_container


@pytest.fixture(scope='session')
def awx_server_no_wait(container_factory, base_path):
    """
    The container options used here mirror the Makefile docker-runner target
    Additional customizations include:
     - bootstrapping migrations, install, db, cache, etc. with custom settings and script
     - networking so that server can be accessed, and container can talk to other local containers
    """
    org = os.getenv('DEV_DOCKER_OWNER', 'ansible').lower()
    tag = os.getenv('COMPOSE_TAG', 'devel')
    image_name = f'ghcr.io/{org}/awx_devel:{tag}'
    print(f'Using AWX image {image_name}')
    return container_factory(
        image_name,
        dict(
            user=os.getuid(),
            # ports={'8045/tcp': '8045'},  # need if you do not use host network_mode
            environment=['AWX_LOGGING_MODE=stdout'],  # superuser created in migration hack
            volumes={
                base_path: {'bind': '/awx_devel', 'mode': 'rw'},
                f'{base_path}/tools/test/minimal_settings.py': {'bind': '/etc/tower/conf.d/minimal_settings.py', 'mode': 'rw'},
            },
            name='hack_awx_1',
            network_mode='host',  # to talk to the other containers
        ),
        command='/awx_devel/tools/test/test_server.sh awx-python manage.py runserver 8045',
    )


@pytest.fixture(scope='session')
def awx_server(awx_server_no_wait):
    print('Waiting for AWX to be running')
    for i in range(30):
        try:
            r = requests.get('http://localhost:8045/api/v2/', verify=False, timeout=5)
        except Exception:
            time.sleep(1)
            print('.')
            continue
        print('\nserver is up and running now')
        assert "system_job_templates" in r.text  # minimal sanity assertion
        break
    else:
        raise Exception('AWX sever never came up')
    return awx_server_no_wait


@pytest.fixture(scope='session')
def v2(awx_server):
    url = 'http://localhost:8045/'
    conn = Connection(url, verify=False)
    conn.login(username='admin', password='password')
    return get_registered_page('/api/v2/')(conn, endpoint='/api/v2/').get()
