import pytest

from awxkit.exceptions import Unauthorized
from awxkit.awx.utils import as_user


def test_login_as_invalid_user(v2):
    with as_user(v2.connection, username='fake_user', password='fake_pass'):
        with pytest.raises(Unauthorized):
            v2.me.get()
