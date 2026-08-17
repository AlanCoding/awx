"""Tests for project creation with reverse sync to gateway.

Reconstructs the ATF integration test flow for AAP-82221 by mocking the
inter-service HTTP call from controller to gateway. The goal is to identify
what error the gateway sync path produces and whether it matches the 403
seen in ATF.

KEY FINDINGS:
- Project is NOT a resource model (only Team, Org, User, RoleDefinition, AAPFlag).
  No resource object sync fires on project creation.
- give_creator_permissions returns early when the user already has all
  creator-default permissions via the org role (change, delete, update, use, view).
  No assignment sync fires either.
- Therefore, for an Org Project Admin user, project creation produces ZERO
  outgoing HTTP calls to the gateway.  The ATF 403 cannot be from a sync path.
"""

import uuid
from unittest import mock

import pytest
import requests
from django.test.utils import override_settings

from awx.api.versioning import reverse
from awx.main.models import Organization, Project, Team

from ansible_base.rbac import permission_registry
from ansible_base.rbac.claims import save_user_claims
from ansible_base.rbac.models import RoleDefinition, RoleEvaluation, RoleTeamAssignment
from ansible_base.resource_registry import apps as rr_apps
from ansible_base.resource_registry.signals.handlers import get_resource_models

OLD_ORG_PROJECT_ADMIN_PERMS = [
    'add_project',
    'change_project',
    'delete_project',
    'update_project',
    'use_project',
    'view_organization',
    'view_project',
]

RESOURCE_SERVER_SETTINGS = {
    'RESOURCE_SERVER': {
        'URL': 'https://gateway.example.invalid',
        'SECRET_KEY': 'test-secret-key',
        'VALIDATE_HTTPS': False,
    },
    'RESOURCE_SERVICE_PATH': '/api/v1/service-index/',
}


def _setup_org_project_admin(rando, organization, team):
    """Give rando the old Org Project Admin role (without member_organization) via team."""
    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )
    member_rd = RoleDefinition.objects.get(name='Team Member')
    member_rd.give_permission(rando, team)
    rd.give_permission(team, organization)
    return rd


def _make_mock_response(status_code=201, json_data=None):
    resp = mock.Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data or {})
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} Error", response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.mark.django_db
def test_org_project_admin_via_team_can_create_project(post, setup_managed_roles, organization, team, rando):
    """Baseline: use the actual 'Organization Project Admin' managed role,
    give it to a team on an org, make rando a team member, create a project.
    This is the closest reproduction of the ATF scenario using direct
    controller-side role assignment."""
    org_project_admin_rd = RoleDefinition.objects.get(name='Organization Project Admin')
    org_project_admin_rd.give_permission(team, organization)

    team_member_rd = RoleDefinition.objects.get(name='Team Member')
    team_member_rd.give_permission(rando, team)

    # Verify DAB RBAC
    has_add = RoleEvaluation.has_obj_perm(rando, organization, 'add_project')
    all_perms = sorted(RoleEvaluation.get_permissions(rando, organization))
    print(f"\n*** has_obj_perm(rando, org, 'add_project') = {has_add} ***")
    print(f"*** All org permissions: {all_perms} ***")

    response = post(
        reverse('api:project_list'),
        data={
            'name': 'test-org-project-admin-via-team',
            'organization': organization.id,
            'scm_type': 'git',
            'scm_url': 'https://github.com/ansible/test-playbooks.git',
        },
        user=rando,
        expect=201,
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_project_is_not_a_resource_model(setup_managed_roles):
    """Project is not in the resource registry, so no post_save resource sync
    fires when a project is created.  This rules out the resource object sync
    as the source of the ATF 403."""
    resource_models = list(get_resource_models())
    assert Project not in resource_models


@pytest.mark.django_db
def test_creator_permissions_skipped_when_user_already_has_perms(post, setup_managed_roles, organization, team, rando):
    """The Org Project Admin role already gives change/delete/update/use/view
    on child projects.  give_creator_permissions checks what the user has and
    skips if nothing new is needed — no assignment reverse-sync fires."""
    _setup_org_project_admin(rando, organization, team)

    with mock.patch('ansible_base.rbac.sync.maybe_reverse_sync_assignment') as mock_sync:
        post(
            reverse('api:project_list'),
            data={
                'name': 'test-creator-skip',
                'organization': organization.id,
                'scm_type': 'git',
                'scm_url': 'https://github.com/ansible/test-playbooks.git',
            },
            user=rando,
            expect=201,
        )

        assert not mock_sync.called, "give_creator_permissions should NOT have synced — user already " "has all creator permissions via the org role"

    project = Project.objects.get(name='test-creator-skip')
    has_perms = set(RoleEvaluation.get_permissions(rando, project))
    for action in ['change', 'delete', 'update', 'use', 'view']:
        assert f'{action}_project' in has_perms, f"Missing {action}_project"


@pytest.mark.django_db
@override_settings(**RESOURCE_SERVER_SETTINGS)
def test_zero_sync_calls_on_project_creation(post, setup_managed_roles, organization, team, rando):
    """With RESOURCE_SERVER configured and signals connected, creating a project
    as Org Project Admin produces zero outgoing HTTP calls to the gateway.
    Project is not a resource model (no object sync) and the user already has
    all creator permissions (no assignment sync)."""
    _setup_org_project_admin(rando, organization, team)

    with mock.patch('ansible_base.resource_registry.rest_client.ResourceAPIClient._make_request') as mock_request:
        mock_request.return_value = _make_mock_response(201, {'ansible_id': str(uuid.uuid4()), 'service_id': str(uuid.uuid4())})

        rr_apps.connect_resource_signals(sender=None)
        try:
            post(
                reverse('api:project_list'),
                data={
                    'name': 'test-zero-sync',
                    'organization': organization.id,
                    'scm_type': 'git',
                    'scm_url': 'https://github.com/ansible/test-playbooks.git',
                },
                user=rando,
                expect=201,
            )
        finally:
            rr_apps.disconnect_resource_signals(sender=None)

        assert not mock_request.called, f"Expected zero sync calls but got: " f"{[(c[0][0], c[0][1]) for c in mock_request.call_args_list]}"


@pytest.mark.django_db
def test_no_sync_without_resource_server(post, setup_managed_roles, organization, team, rando):
    """Without RESOURCE_SERVER configured, no sync request is made.
    This confirms our existing passing tests never exercise the sync path."""
    _setup_org_project_admin(rando, organization, team)

    with mock.patch('ansible_base.resource_registry.rest_client.ResourceAPIClient._make_request') as mock_request:
        post(
            reverse('api:project_list'),
            data={
                'name': 'test-no-sync-project',
                'organization': organization.id,
                'scm_type': 'git',
                'scm_url': 'https://github.com/ansible/test-playbooks.git',
            },
            user=rando,
            expect=201,
        )

        assert not mock_request.called


@pytest.mark.django_db
def test_sync_fires_when_user_lacks_creator_perms(post, setup_managed_roles, organization, rando):
    """When the user has only add_project (but NOT change/delete/etc.),
    give_creator_permissions DOES create a creator role and fires the sync.
    This simulates a minimal permission scenario."""
    minimal_perms = ['add_project', 'view_organization', 'view_project']
    rd, _ = RoleDefinition.objects.get_or_create(
        name='minimal-org-project-adder',
        permissions=minimal_perms,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )
    rd.give_permission(rando, organization)

    with mock.patch('ansible_base.rbac.models.role.maybe_reverse_sync_assignment') as mock_sync:
        post(
            reverse('api:project_list'),
            data={
                'name': 'test-sync-fires',
                'organization': organization.id,
                'scm_type': 'git',
                'scm_url': 'https://github.com/ansible/test-playbooks.git',
            },
            user=rando,
            expect=201,
        )

        assert mock_sync.called, (
            "give_creator_permissions should have synced — user lacks " "change/delete/update/use permissions that creator defaults require"
        )


@pytest.mark.django_db
@override_settings(**RESOURCE_SERVER_SETTINGS)
def test_sync_403_propagates_not_as_403(post, setup_managed_roles, organization, rando):
    """When the assignment sync fires and the gateway returns 403, the error
    propagates as an unhandled HTTPError through the no-try/except chain.
    DRF translates this to a non-403 status (likely 500).
    This proves the ATF 403 is not from a sync failure."""
    minimal_perms = ['add_project', 'view_organization', 'view_project']
    rd, _ = RoleDefinition.objects.get_or_create(
        name='minimal-org-project-adder-403',
        permissions=minimal_perms,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )
    rd.give_permission(rando, organization)

    with mock.patch('ansible_base.resource_registry.service_client.requests.request') as mock_http:
        mock_resp = _make_mock_response(403, {'detail': 'You do not have permission to perform this action.'})
        mock_http.return_value = mock_resp

        # The post fixture raises exceptions instead of returning 500
        # responses, so we catch directly to observe the error type
        try:
            response = post(
                reverse('api:project_list'),
                data={
                    'name': 'test-sync-403-propagates',
                    'organization': organization.id,
                    'scm_type': 'git',
                    'scm_url': 'https://github.com/ansible/test-playbooks.git',
                },
                user=rando,
            )
            # If we get here, the error was swallowed or converted
            print(f"\n*** SYNC 403 → controller returned {response.status_code} ***")
            assert response.status_code != 403, "If sync 403 propagates as 403 to the consumer, " "there's a path converting HTTPError to PermissionDenied"
        except requests.exceptions.HTTPError as e:
            # The HTTPError propagates unhandled — in production DRF would
            # turn this into a 500 Internal Server Error, NOT a 403.
            print(f"\n*** SYNC 403 → HTTPError propagated: {e} ***")
            assert '403' in str(e)
        except Exception as e:
            # Some other exception — what is it?
            print(f"\n*** SYNC 403 → {type(e).__name__}: {e} ***")
            raise


@pytest.mark.django_db
def test_jwt_claims_path_grants_add_project(post, setup_managed_roles, organization, team, rando):
    """Simulate the JWT claims authentication path:
    1. Team has 'Organization Project Admin' on org (RoleTeamAssignment - exists at controller)
    2. JWT claims include 'Team Member' for user -> team (simulating gateway claims)
    3. save_user_claims processes claims (as AwxJWTAuthentication would)
    4. User should have add_project on org through the team chain
    5. User should be able to create a project

    This tests whether the JWT claims path correctly propagates team-based
    org permissions through DAB RBAC."""
    # Step 1: Assign "Organization Project Admin" to team on org
    # This simulates what exists at the controller before user authenticates
    org_ct = permission_registry.content_type_model.objects.get_for_model(Organization)
    org_project_admin_rd = RoleDefinition.objects.get(name='Organization Project Admin')
    org_project_admin_rd.give_permission(team, organization)

    # Verify the team assignment exists
    assert RoleTeamAssignment.objects.filter(
        team=team,
        role_definition=org_project_admin_rd,
        object_id=organization.pk,
    ).exists(), "RoleTeamAssignment should exist"

    # Step 2: Build claims as the gateway would send them
    # Only managed roles are in claims: Team Member, Organization Member, etc.
    # Ensure resource entries exist (the test fixtures don't always create them)
    from ansible_base.resource_registry.models import Resource
    from django.contrib.contenttypes.models import ContentType

    for obj in (organization, team):
        ct = ContentType.objects.get_for_model(obj)
        Resource.objects.get_or_create(object_id=obj.pk, content_type=ct, defaults={'name': obj.name})
    organization.refresh_from_db()
    team.refresh_from_db()
    org_ansible_id = str(organization.resource.ansible_id)
    team_ansible_id = str(team.resource.ansible_id)

    objects = {
        'organization': [{'ansible_id': org_ansible_id, 'name': organization.name}],
        'team': [{'ansible_id': team_ansible_id, 'name': team.name, 'org': 0}],
    }
    object_roles = {
        'Team Member': {
            'content_type': 'team',
            'objects': [0],
        },
    }
    global_roles = []

    # Step 3: Process claims as save_user_claims would (fire_signals_on_create=False)
    save_user_claims(rando, objects, object_roles, global_roles)

    # Step 4: Check DAB RBAC - does user have add_project on org?
    has_add_project = RoleEvaluation.has_obj_perm(rando, organization, 'add_project')
    print(f"\n*** has_obj_perm(rando, org, 'add_project') = {has_add_project} ***")

    # Also check all permissions the user has on the org
    all_perms = set(RoleEvaluation.get_permissions(rando, organization))
    print(f"*** All permissions on org: {sorted(all_perms)} ***")

    assert has_add_project, (
        f"User should have add_project on org through Team Member -> " f"Organization Project Admin chain. Got permissions: {sorted(all_perms)}"
    )

    # Step 5: Try to create a project via the API
    response = post(
        reverse('api:project_list'),
        data={
            'name': 'test-jwt-claims-project',
            'organization': organization.id,
            'scm_type': 'git',
            'scm_url': 'https://github.com/ansible/test-playbooks.git',
        },
        user=rando,
        expect=201,
    )
    assert response.status_code == 201, f"Project creation failed with {response.status_code}. " f"User permissions on org: {sorted(all_perms)}"


@pytest.mark.django_db
def test_jwt_claims_path_without_team_assignment_denies(post, setup_managed_roles, organization, team, rando):
    """Without the RoleTeamAssignment at the controller, JWT claims with
    Team Member should NOT grant add_project. This is the baseline."""
    from ansible_base.resource_registry.models import Resource
    from django.contrib.contenttypes.models import ContentType

    for obj in (organization, team):
        ct = ContentType.objects.get_for_model(obj)
        Resource.objects.get_or_create(object_id=obj.pk, content_type=ct, defaults={'name': obj.name})
    organization.refresh_from_db()
    team.refresh_from_db()
    org_ansible_id = str(organization.resource.ansible_id)
    team_ansible_id = str(team.resource.ansible_id)

    objects = {
        'organization': [{'ansible_id': org_ansible_id, 'name': organization.name}],
        'team': [{'ansible_id': team_ansible_id, 'name': team.name, 'org': 0}],
    }
    object_roles = {
        'Team Member': {
            'content_type': 'team',
            'objects': [0],
        },
    }

    save_user_claims(rando, objects, object_roles, [])

    has_add_project = RoleEvaluation.has_obj_perm(rando, organization, 'add_project')
    print(f"\n*** Without team assignment: has_obj_perm(rando, org, 'add_project') = {has_add_project} ***")

    assert not has_add_project, "User should NOT have add_project without team->org assignment"


@pytest.mark.django_db
def test_old_rbac_contains_delegates_to_dab_rbac(setup_managed_roles, organization, team, rando):
    """Role.__contains__ delegates to has_obj_perm when ROLE_SYSTEM_ACTIVATED=True.
    This test verifies that the old RBAC check used by check_related/can_add
    correctly uses DAB RBAC, not the old ancestors table."""
    from django.conf import settings

    assert settings.ANSIBLE_BASE_ROLE_SYSTEM_ACTIVATED is True

    # Set up team->org assignment (controller-side)
    org_project_admin_rd = RoleDefinition.objects.get(name='Organization Project Admin')
    org_project_admin_rd.give_permission(team, organization)

    # Simulate claims
    from ansible_base.resource_registry.models import Resource
    from django.contrib.contenttypes.models import ContentType

    for obj in (organization, team):
        ct = ContentType.objects.get_for_model(obj)
        Resource.objects.get_or_create(object_id=obj.pk, content_type=ct, defaults={'name': obj.name})
    organization.refresh_from_db()
    team.refresh_from_db()
    org_ansible_id = str(organization.resource.ansible_id)
    team_ansible_id = str(team.resource.ansible_id)
    objects = {
        'organization': [{'ansible_id': org_ansible_id, 'name': organization.name}],
        'team': [{'ansible_id': team_ansible_id, 'name': team.name, 'org': 0}],
    }
    object_roles = {'Team Member': {'content_type': 'team', 'objects': [0]}}
    save_user_claims(rando, objects, object_roles, [])

    # Verify old RBAC __contains__ delegates to DAB RBAC
    result = rando in organization.project_admin_role
    print(f"\n*** rando in org.project_admin_role = {result} ***")
    assert result, "Old RBAC __contains__ should delegate to has_obj_perm and return True"

    # Also verify the old RBAC sync path
    from ansible_base.jwt_consumer.awx.auth import AwxJWTAuthentication

    auth = AwxJWTAuthentication()
    auth._sync_old_rbac(rando, objects, object_roles)

    # After old RBAC sync, user should be in team.member_role
    assert rando in team.member_role, "User should be direct member of team.member_role"

    # And still pass the DAB RBAC check
    assert RoleEvaluation.has_obj_perm(rando, organization, 'add_project')
