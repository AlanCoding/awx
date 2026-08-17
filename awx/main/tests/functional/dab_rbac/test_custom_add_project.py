import pytest
from rest_framework.exceptions import PermissionDenied

from awx.api.versioning import reverse
from awx.main.access import ProjectAccess
from awx.main.models import Organization, Project

from ansible_base.rbac.models import RoleDefinition, RoleEvaluation
from ansible_base.rbac.policies import check_content_obj_permission
from ansible_base.rbac.remote import RemoteObject
from ansible_base.rbac import permission_registry

OLD_ORG_PROJECT_ADMIN_PERMS = [
    'add_project',
    'change_project',
    'delete_project',
    'update_project',
    'use_project',
    'view_organization',
    'view_project',
]


@pytest.mark.django_db
def test_old_org_project_admin_via_team(setup_managed_roles, organization, team, rando):
    """Reproduce AAP-82221: stand-in for old Organization Project Admin
    (without member_organization), given to a team."""

    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )

    member_rd = RoleDefinition.objects.get(name='Team Member')
    member_rd.give_permission(rando, team)

    rd.give_permission(team, organization)

    # DAB level: user has add_project
    assert rando.has_obj_perm(organization, 'add_project')

    # AWX access layer: can_add works
    access = ProjectAccess(rando)
    assert access.can_add(None)
    assert access.can_add({'organization': organization.id})


@pytest.mark.django_db
def test_check_content_obj_permission_with_add_project(setup_managed_roles, organization, team, rando):
    """check_content_obj_permission requires change_organization, but the user
    only has add_project. This is the 'duplicate permission check' from the
    service-index sync path."""

    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )

    member_rd = RoleDefinition.objects.get(name='Team Member')
    member_rd.give_permission(rando, team)

    rd.give_permission(team, organization)

    # User has add_project but NOT change_organization
    assert rando.has_obj_perm(organization, 'add_project')
    assert not rando.has_obj_perm(organization, 'change_organization')

    # check_content_obj_permission demands change_organization on the org
    with pytest.raises(PermissionDenied):
        check_content_obj_permission(rando, organization)


@pytest.mark.django_db
def test_check_content_obj_permission_remote_project(setup_managed_roles, organization, team, rando):
    """Simulate the gateway side: give_creator_permissions syncs a creator role
    assignment for a brand-new project to gateway. At the gateway the project is
    a RemoteObject. The service-index serializer calls
    check_content_obj_permission(requesting_user, remote_project).

    The RemoteObject path checks change_project on the project itself, but the
    user only has add_project on the parent org (and no permissions on the
    project yet — the creator role is being synced right now).

    This is the real cause of the 403 in AAP-82221."""

    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )

    member_rd = RoleDefinition.objects.get(name='Team Member')
    member_rd.give_permission(rando, team)
    rd.give_permission(team, organization)

    # User CAN add projects (the controller side is fine)
    assert rando.has_obj_perm(organization, 'add_project')
    access = ProjectAccess(rando)
    assert access.can_add({'organization': organization.id})

    # Now simulate the gateway side: the project was just created and its
    # creator role assignment is being synced.  At the gateway, the project
    # doesn't exist locally — it's a RemoteObject.
    project_ct = permission_registry.content_type_model.objects.get_for_model(Project)
    remote_project = RemoteObject(content_type=project_ct, object_id=99999)

    # The user has NO permissions on this specific project yet
    assert not rando.has_obj_perm(remote_project, 'change')

    # check_content_obj_permission (RemoteObject path) demands change_project
    with pytest.raises(PermissionDenied):
        check_content_obj_permission(rando, remote_project)


@pytest.mark.django_db
def test_create_project_via_api_old_org_project_admin(post, setup_managed_roles, organization, team, rando):
    """POST to the project list endpoint as a user who has the old
    Organization Project Admin role (without member_organization) via a team.
    This exercises the full DRF view layer including permission classes."""

    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )

    member_rd = RoleDefinition.objects.get(name='Team Member')
    member_rd.give_permission(rando, team)
    rd.give_permission(team, organization)

    post(
        reverse('api:project_list'),
        data={
            'name': 'test-project-old-org-admin',
            'organization': organization.id,
            'scm_type': 'git',
            'scm_url': 'https://github.com/ansible/test-playbooks.git',
        },
        user=rando,
        expect=201,
    )


@pytest.mark.django_db
def test_create_project_via_api_old_org_project_admin_direct_user(post, setup_managed_roles, organization, rando):
    """Same as above but with a direct user assignment (no team), matching
    the test_user_can_create_projects_with_role integration test."""

    rd, _ = RoleDefinition.objects.get_or_create(
        name='old-org-project-admin',
        permissions=OLD_ORG_PROJECT_ADMIN_PERMS,
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )

    rd.give_permission(rando, organization)

    post(
        reverse('api:project_list'),
        data={
            'name': 'test-project-old-org-admin-direct',
            'organization': organization.id,
            'scm_type': 'git',
            'scm_url': 'https://github.com/ansible/test-playbooks.git',
        },
        user=rando,
        expect=201,
    )
