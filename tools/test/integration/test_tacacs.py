import os
import json
import time

import pytest

from awxkit.awx.utils import as_user
from awxkit.exceptions import Unauthorized, BadRequest


@pytest.fixture(scope='class')
def tacacs_server_no_wait(container_factory):
    return container_factory('dchidell/docker-tacacs', dict(ports={'49/tcp': '49'}, name='hack_tacacs_1'))


@pytest.fixture(scope='class')
def tacacs_server(tacacs_server_no_wait):
    return tacacs_server_no_wait


@pytest.fixture(scope='session')
def tacacs_settings(base_path):
    settings_path = os.path.join(base_path, 'tools/docker-compose/ansible/templates/tacacsplus_settings.json.j2')
    with open(settings_path, 'r') as f:
        data = json.load(f)
    data["TACACSPLUS_HOST"] = "127.0.0.1"
    return data


def test_confirm_tacacs_host_and_secret_required(v2):
    settings_pg = v2.settings.get().get_endpoint('tacacsplus')
    with pytest.raises(BadRequest) as e:
        settings_pg.patch(TACACSPLUS_HOST='127.0.0.1')
    assert e.value.msg == {'__all__': ['TACACSPLUS_SECRET is required when TACACSPLUS_HOST is provided.']}


def test_timeout_of_tacacs(request, v2, tacacs_settings):
    user = v2.users.create(username='iosadmin', password='cisco', is_superuser=False)
    request.addfinalizer(user.silent_delete)

    setting_pg = v2.settings.get().get_endpoint('tacacsplus')
    request.addfinalizer(setting_pg.silent_delete)
    new_settings = tacacs_settings.copy()
    new_settings.update(dict(TACACSPLUS_HOST='169.254.1.0', TACACSPLUS_SESSION_TIMEOUT=20))
    setting_pg.patch(**new_settings)

    start = time.time()
    # AWX should first attempt to authenticate using TACACS+ server, then use local login
    with as_user(v2.connection, username='iosadmin', password='cisco'):
        v2.me.get()
    login_time = time.time() - start

    assert login_time > 20
    assert login_time < 25


class TestTACACSPlus:
    """
    Integration testing with AWX and TACACS Plus, where integration is pre-configured
    TODO:
     - using ascii vs pap protocol
    """

    @pytest.fixture(scope='class', autouse=True)
    def plumb_tacacs(self, request, v2, tacacs_settings, tacacs_server):
        setting_pg = v2.settings.get().get_endpoint('tacacsplus')
        request.addfinalizer(setting_pg.silent_delete)
        setting_pg.patch(**tacacs_settings)

    def test_login_as_new_user(self, request, v2):
        assert not v2.users.get(username='iosadmin').count

        # Core test assertion - accounts are from
        # https://hub.docker.com/r/dchidell/docker-tacacs
        with as_user(v2.connection, username='iosadmin', password='cisco'):
            me_page = v2.me.get()
            user = me_page.results[0].get()
            assert 'iosadmin' == user.username
            request.addfinalizer(user.silent_delete)

        assert len(v2.users.get(username='iosadmin').results) == 1

    def test_username_change_with_tacacs_auth(self, request, v2):
        assert not v2.users.get(username='iosadmin').count

        with as_user(v2.connection, username='iosadmin', password='cisco'):
            user = v2.me.get().results.pop()
            request.addfinalizer(user.silent_delete)
            first_user_id = user.id
            user.first_name = 'changed'
            v2.connection.logout()

        with as_user(v2.connection, username='iosadmin', password='cisco'):
            user = v2.me.get().results.pop()
            assert first_user_id == user.id
            assert user.get().first_name == 'changed'

    def test_login_as_pre_existing_user(self, request, v2):
        """
        If the user has already been created with a different password as a manual user
        then the username-password from TACACS Plus should not work
        and the normal username-password should continue to work
        """
        user = v2.users.create(username='iosadmin', password='random_password', is_superuser=False)
        request.addfinalizer(user.silent_delete)

        with as_user(v2.connection, username='iosadmin', password='cisco'):
            with pytest.raises(Unauthorized):
                v2.me.get()

        with as_user(v2.connection, username='iosadmin', password='random_password'):
            v2.me.get()

    def test_invalid_user_with_tacacs_plus_enabled(self, v2):
        with as_user(v2.connection, username='fake_user', password='fake_pass'):
            with pytest.raises(Unauthorized):
                v2.me.get()

    def test_cannot_change_password_for_tacacs_user_in_AWX(self, request, v2):
        assert not v2.users.get(username='iosadmin').count

        with as_user(v2.connection, username='iosadmin', password='cisco'):
            user = v2.users.get(username='iosadmin').results.pop()
            request.addfinalizer(user.silent_delete)
            user.patch(password='shouldntw0rk')

        with pytest.raises(Unauthorized):
            with as_user(v2.connection, username='iosadmin', password='shouldntw0rk'):
                v2.me.get()

        with as_user(v2.connection, username='iosadmin', password='cisco'):
            v2.me.get()
