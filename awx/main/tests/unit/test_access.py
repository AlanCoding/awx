import pytest
from unittest import mock

from django.contrib.auth.models import User
from django.forms.models import model_to_dict
from django.core.exceptions import FieldDoesNotExist

from rest_framework.exceptions import ParseError

from awx.main.access import (
    BaseAccess,
    BaseAttachAccess,
    check_superuser,
    JobTemplateAccess,
    WorkflowJobTemplateAccess,
    SystemJobTemplateAccess,
    ProjectAccess,
    ActivityStreamAccess,
    vars_are_encrypted
)

from awx.main.models import (
    Credential,
    CredentialType,
    Inventory,
    Project,
    Role,
    Organization,
    ActivityStream,
    Job,
    JobTemplate,
    SystemJobTemplate
)


@pytest.fixture
def user_unit():
    return User(username='rando', password='raginrando', email='rando@redhat.com')


class TestRelatedFieldAccess:
    @pytest.fixture
    def resource_good(self, mocker):
        good_role = mocker.MagicMock(__contains__=lambda self, user: True)
        return mocker.MagicMock(related=mocker.MagicMock(admin_role=good_role),
                                admin_role=good_role)

    @pytest.fixture
    def resource_bad(self, mocker):
        bad_role = mocker.MagicMock(__contains__=lambda self, user: False)
        return mocker.MagicMock(related=mocker.MagicMock(admin_role=bad_role),
                                admin_role=bad_role)

    @pytest.fixture
    def access(self, user_unit):
        return BaseAccess(user_unit)

    def test_new_optional_fail(self, access, resource_bad, mocker):
        """
        User tries to create a new resource, but lacks permission
        to the related resource they provided
        """
        data = {'related': resource_bad}
        assert not access.check_related('related', mocker.MagicMock, data)

    def test_new_with_bad_data(self, access, mocker):
        data = {'related': 3.1415}
        with pytest.raises(ParseError):
            access.check_related('related', mocker.MagicMock(), data)

    def test_new_mandatory_fail(self, access, mocker):
        access.user.is_superuser = False
        assert not access.check_related(
            'related', mocker.MagicMock, {}, mandatory=True)
        assert not access.check_related(
            'related', mocker.MagicMock, {'resource': None}, mandatory=True)

    def test_existing_no_op(self, access, resource_bad, mocker):
        """
        User edits a resource, but does not change related field
        lack of access to related field does not block action
        """
        data = {'related': resource_bad.related}
        assert access.check_related(
            'related', mocker.MagicMock, data, obj=resource_bad)
        assert access.check_related(
            'related', mocker.MagicMock, {}, obj=resource_bad)

    def test_existing_required_access(self, access, resource_bad, mocker):
        # no-op actions, but mandatory kwarg requires check to pass
        assert not access.check_related(
            'related', mocker.MagicMock, {}, obj=resource_bad, mandatory=True)
        assert not access.check_related(
            'related', mocker.MagicMock, {'related': resource_bad.related},
            obj=resource_bad, mandatory=True)

    def test_existing_no_access_to_current(
            self, access, resource_good, resource_bad, mocker):
        """
        User gives a valid related resource (like organization), but does
        not have access to _existing_ related resource, so deny action
        """
        data = {'related': resource_good}
        assert not access.check_related(
            'related', mocker.MagicMock, data, obj=resource_bad)

    def test_existing_no_access_to_new(
            self, access, resource_good, resource_bad, mocker):
        data = {'related': resource_bad}
        assert not access.check_related(
            'related', mocker.MagicMock, data, obj=resource_good)

    def test_existing_not_allowed_to_remove(self, access, resource_bad, mocker):
        data = {'related': None}
        assert not access.check_related(
            'related', mocker.MagicMock, data, obj=resource_bad)

    def test_existing_not_null_null(self, access, mocker):
        resource = mocker.MagicMock(related=None)
        data = {'related': None}
        # Not changing anything by giving null when it is already-null
        # important for PUT requests
        assert access.check_related(
            'related', mocker.MagicMock, data, obj=resource, mandatory=True)


def test_encrypted_vars_detection():
    assert vars_are_encrypted({
        'aaa': {'b': 'c'},
        'alist': [],
        'test_var_eight': '$encrypted$UTF8$AESCBC$Z0FBQUF...==',
        'test_var_five': 'four',
    })
    assert not vars_are_encrypted({
        'aaa': {'b': 'c'},
        'alist': [],
        'test_var_five': 'four',
    })


@pytest.fixture
def job_template_with_ids(job_template_factory):
    # Create non-persisted objects with IDs to send to job_template_factory
    ssh_type = CredentialType(kind='ssh')
    credential = Credential(id=1, pk=1, name='testcred', credential_type=ssh_type)

    net_type = CredentialType(kind='net')
    net_cred = Credential(id=2, pk=2, name='testnetcred', credential_type=net_type)

    cloud_type = CredentialType(kind='aws')
    cloud_cred = Credential(id=3, pk=3, name='testcloudcred', credential_type=cloud_type)

    inv = Inventory(id=11, pk=11, name='testinv')
    proj = Project(id=14, pk=14, name='testproj')

    jt_objects = job_template_factory(
        'testJT', project=proj, inventory=inv, credential=credential,
        cloud_credential=cloud_cred, network_credential=net_cred,
        persisted=False)
    return jt_objects.job_template


def test_superuser(mocker):
    user = mocker.MagicMock(spec=User, id=1, is_superuser=True)
    access = BaseAccess(user)

    can_add = check_superuser(BaseAccess.can_add)
    assert can_add(access, None) is True


def test_not_superuser(mocker):
    user = mocker.MagicMock(spec=User, id=1, is_superuser=False)
    access = BaseAccess(user)

    can_add = check_superuser(BaseAccess.can_add)
    assert can_add(access, None) is False


def test_jt_existing_values_are_nonsensitive(job_template_with_ids, user_unit):
    """Assure that permission checks are not required if submitted data is
    identical to what the job template already has."""

    data = model_to_dict(job_template_with_ids, exclude=['unifiedjobtemplate_ptr'])
    access = JobTemplateAccess(user_unit)

    assert access.changes_are_non_sensitive(job_template_with_ids, data)


def test_change_jt_sensitive_data(job_template_with_ids, mocker, user_unit):
    """Assure that can_add is called with all ForeignKeys."""

    job_template_with_ids.admin_role = Role()

    data = {'inventory': job_template_with_ids.inventory.id + 1}
    access = JobTemplateAccess(user_unit)

    mock_add = mock.MagicMock(return_value=False)
    with mock.patch('awx.main.models.rbac.Role.__contains__', return_value=True):
        with mocker.patch('awx.main.access.JobTemplateAccess.can_add', mock_add):
            with mocker.patch('awx.main.access.JobTemplateAccess.can_read', return_value=True):
                assert not access.can_change(job_template_with_ids, data)

    mock_add.assert_called_once_with({
        'inventory': data['inventory'],
        'project': job_template_with_ids.project.id
    })


def test_jt_add_scan_job_check(job_template_with_ids, user_unit):
    "Assure that permissions to add scan jobs work correctly"

    access = JobTemplateAccess(user_unit)
    project = job_template_with_ids.project
    inventory = job_template_with_ids.inventory
    project.use_role = Role()
    inventory.use_role = Role()
    organization = Organization(name='test-org')
    inventory.organization = organization
    organization.admin_role = Role()

    def mock_get_object(Class, **kwargs):
        if Class == Project:
            return project
        elif Class == Inventory:
            return inventory
        else:
            raise Exception('Item requested has not been mocked')


    with mock.patch('awx.main.models.rbac.Role.__contains__', return_value=True):
        with mock.patch('awx.main.access.get_object_or_400', mock_get_object):
            assert access.can_add({
                'project': project.pk,
                'inventory': inventory.pk,
                'job_type': 'scan'
            })


def mock_raise_none(self, add_host=False, feature=None, check_expiration=True):
    return None


def test_jt_can_add_bad_data(user_unit):
    "Assure that no server errors are returned if we call JT can_add with bad data"
    access = JobTemplateAccess(user_unit)
    assert not access.can_add({'asdf': 'asdf'})


class TestWorkflowAccessMethods:
    @pytest.fixture
    def workflow(self, workflow_job_template_factory):
        objects = workflow_job_template_factory('test_workflow', persisted=False)
        return objects.workflow_job_template

    def test_workflow_can_add(self, workflow, user_unit):
        organization = Organization(name='test-org')
        workflow.organization = organization
        organization.workflow_admin_role = Role()

        def mock_get_object(Class, **kwargs):
            if Class == Organization:
                return organization
            else:
                raise Exception('Item requested has not been mocked')

        access = WorkflowJobTemplateAccess(user_unit)
        with mock.patch('awx.main.models.rbac.Role.__contains__', return_value=True):
            with mock.patch('awx.main.access.get_object_or_400', mock_get_object):
                assert access.can_add({'organization': 1})



def test_user_capabilities_method():
    """Unit test to verify that the user_capabilities method will defer
    to the appropriate sub-class methods of the access classes.
    Note that normal output is True/False, but a string is returned
    in these tests to establish uniqueness.
    """

    class FooAccess(BaseAccess):
        def can_change(self, obj, data):
            return 'bar'

        def can_copy(self, obj):
            return 'foo'

    user = User(username='auser')
    foo_access = FooAccess(user)
    foo = object()
    foo_capabilities = foo_access.get_user_capabilities(foo, ['edit', 'copy'])
    assert foo_capabilities == {
        'edit': 'bar',
        'copy': 'foo'
    }


def test_system_job_template_can_start(mocker):
    user = mocker.MagicMock(spec=User, id=1, is_system_auditor=True, is_superuser=False)
    assert user.is_system_auditor
    access = SystemJobTemplateAccess(user)
    assert not access.can_start(None)

    user.is_superuser = True
    access = SystemJobTemplateAccess(user)
    assert access.can_start(None)


class TestAttachUtilities:
    def test_relationship_not_editable(self):
        with pytest.raises(RuntimeError) as exe:
            # valid relationship but not editable by user, should error
            ActivityStreamAccess(User()).can_attach(ActivityStream(id=42), Job(), 'job')
        assert 'has not be written' in exe.value.args[0]

    def test_relationship_does_not_exist(self):
        with pytest.raises(FieldDoesNotExist):
            # relationship not valid, should error
            ActivityStreamAccess(User()).can_attach(ActivityStream(id=42), Job(), 'newspapers')

    def test_valid_field_but_not_editable(self):
        # This case gets weird, a relationship exists technically within the models
        # but for the given model and field, this is not an editable field by the user
        with pytest.raises(RuntimeError) as exe:
            SystemJobTemplateAccess(User()).can_attach(SystemJobTemplate(pk=42), Credential(pk=43), 'credentials')
        assert 'Access logic for either SystemJobTemplate or Credential' in exe.value.args[0]
        assert 'not implemented' in exe.value.args[0]

    def test_bad_sub_object_type(self):
        with pytest.raises(RuntimeError) as exe:
            # valid and editable relationship but wrong type given for object being attached
            JobTemplateAccess(User()).can_attach(JobTemplate(pk=42), Job(pk=43), 'credentials')
        assert 'Incorrect type given' in exe.value.args[0]

    # valid usage
    def test_valid_association_access_call(self, mocker):
        mock_method = mocker.MagicMock(return_value='fooooo')
        with mocker.patch('awx.main.access.RelatedCredentialsAttachAccess.can_add', mock_method):
            assert JobTemplateAccess(User()).can_attach(JobTemplate(pk=42), Credential(pk=43), 'credentials') == 'fooooo'
        mock_method.assert_called_once_with(obj_A=JobTemplate(pk=42), obj_B=Credential(pk=43))

    # valid usage
    def test_valid_association_access_call_in_reverse(self, mocker):
        mock_method = mocker.MagicMock(return_value='fooooo')
        with mocker.patch('awx.main.access.RelatedCredentialsAttachAccess.can_add', mock_method):
            assert JobTemplateAccess(User()).can_attach(Credential(pk=43), JobTemplate(pk=42), 'unifiedjobtemplates') == 'fooooo'
        mock_method.assert_called_once_with(obj_A=JobTemplate(pk=42), obj_B=Credential(pk=43))

    def test_unsupported_relationship_type(self):
        with pytest.raises(RuntimeError):
            # this call makes no sense, and organization has LOTS of project, so what does
            # it mean to attach to this project?
            ProjectAccess(User()).can_attach(Project(pk=42), Organization(pk=43), 'organization')

    # valid usage, but not ideal
    def test_one_to_many_call(self, mocker):
        mock_method = mocker.MagicMock(return_value='baaaar')
        with mocker.patch('awx.main.access.ProjectAccess.can_change', mock_method):
            assert ProjectAccess(User()).can_attach(Organization(pk=43), Project(pk=42), 'projects')
        mock_method.assert_called_once_with(Project(pk=42), {'organization': Organization(pk=43)})

    def test_attach_classes_non_overlapping(self):
        '''Assure that two attach classes will not make claim to the same relationship
        If that happens, that would leave the intention ambiguous and subject to
        unpredictable ordering
        '''
        attach_registry = {}
        for cls in BaseAttachAccess.__subclasses__():
            for through_model in cls.through_models():
                assert through_model not in attach_registry, 'Relationship {} is claimed by both classes {} and {}'.format(
                    through_model.__name__, attach_registry[through_model].__name__, cls.__name__
                )
                attach_registry[through_model] = cls
