import pytest

from django.contrib.auth import get_user_model

from awx.sso.backends import TACACSPlusBackend
from awx.sso.models import UserEnterpriseAuth


@pytest.fixture
def tacacsplus_backend():
    return TACACSPlusBackend()


@pytest.fixture
def existing_normal_user():
    try:
        user = get_user_model().objects.get(username="alice")
    except get_user_model().DoesNotExist:
        user = get_user_model()(username="alice", password="password")
        user.save()
    return user


@pytest.fixture
def existing_tacacsplus_user():
    try:
        user = get_user_model().objects.get(username="foo")
    except get_user_model().DoesNotExist:
        user = get_user_model()(username="foo")
        user.set_unusable_password()
        user.save()
        enterprise_auth = UserEnterpriseAuth(user=user, provider='tacacs+')
        enterprise_auth.save()
    return user
