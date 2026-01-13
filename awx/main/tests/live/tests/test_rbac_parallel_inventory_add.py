import multiprocessing

from django.contrib.auth.models import User
from django.db import connection

from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import RoleDefinition

from awx.api.versioning import reverse
from awx.main.models import Inventory, Organization
from awx.main.tests.functional.conftest import _request


def _parallel_inventory_post(ready_event, continue_event, result_queue, user_id, org_id, inv_name):
    connection.close()
    ready_event.set()
    try:
        post = _request('post')
        user = User.objects.get(id=user_id)
        continue_event.wait()
        response = post(reverse('api:inventory_list'), data={'name': inv_name, 'organization': org_id}, user=user)
        result_queue.put({'user_id': user_id, 'name': inv_name, 'status': response.status_code, 'data': str(getattr(response, 'data', None))})
    except Exception as exc:
        result_queue.put({'user_id': user_id, 'name': inv_name, 'status': 'error', 'data': str(exc)})


def test_parallel_inventory_add_role_does_not_error(organization, user, setup_managed_roles):
    rd, _ = RoleDefinition.objects.get_or_create(
        name='parallel-inventory-add',
        permissions=['add_inventory', 'view_organization'],
        content_type=permission_registry.content_type_model.objects.get_for_model(Organization),
    )
    users = [user(f'parallel-inventory-user-{i}', False) for i in range(3)]
    for actor in users:
        rd.give_permission(actor, organization)

    connection.close()
    ready_events = [multiprocessing.Event() for _ in users]
    continue_event = multiprocessing.Event()
    result_queue = multiprocessing.Queue()

    processes = []
    for idx, actor in enumerate(users):
        inv_name = f'parallel-inventory-{actor.id}'
        proc = multiprocessing.Process(
            target=_parallel_inventory_post,
            args=(ready_events[idx], continue_event, result_queue, actor.id, organization.id, inv_name),
        )
        processes.append(proc)
        proc.start()

    for ready_event in ready_events:
        ready_event.wait()

    continue_event.set()
    for proc in processes:
        proc.join()

    results = [result_queue.get() for _ in users]
    failures = [result for result in results if result['status'] != 201]
    assert not failures, f'Unexpected inventory create results: {failures}'

    user_by_id = {actor.id: actor for actor in users}
    for result in results:
        inventory = Inventory.objects.get(name=result['name'])
        assert user_by_id[result['user_id']].has_obj_perm(inventory, 'change')
