import yaml
import time

from jinja2 import sandbox

from django.core.management.base import BaseCommand

# TODO: remove for cases that do not have this installed
from memory_profiler import profile

from awx.main.models import Inventory, Organization, Group
from awx.main.utils.common import parse_yaml_or_json
from awx.main.tasks.system import delete_inventory, update_smart_memberships_for_inventory
from awx.main.signals import disable_activity_stream


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    return True


def to_bool(a):  # from Ansible
    '''return a bool for the arg'''
    if a is None or isinstance(a, bool):
        return a
    if isinstance(a, str):
        a = a.lower()
    if a in ('yes', 'on', '1', 'true', 1):
        return True
    return False


DEMO_FILTERS = ('name__icontains=host_', 'variables__istartswith=host_marker', 'groups__name__icontains=flavor_4_')

DEMO_TEMPLATES = (
    '{{ "host_" in inventory_hostname }}',  # name__icontains=host_
    '{{ host_marker is defined }}',  # variables__istartswith=host_marker
    '{{ "flavor_4_" in group_names | join("") }}',  # groups__name__icontains=flavor_4_
)


class Command(BaseCommand):

    help = 'Create demo data for smart inventory v2 feature'

    def add_arguments(self, parser):
        parser.add_argument('--sources', dest='sources', type=str2bool, default=True, help='Create the source inventories')
        parser.add_argument('--results', dest='results', type=str2bool, default=True, help='Create the result inventories')
        parser.add_argument('--proposals', dest='proposals', type=str2bool, default=True, help='Run the proposal scripts')

    @profile(precision=6)
    def handle(self, *args, **options):
        with disable_activity_stream():
            org, created = Organization.objects.get_or_create(name='smart_demo')
            print(f'Organization {org.name} being used, created here: {created}')

            if options.get('sources'):
                self.create_source_inventories(org)

            if options.get('results'):
                for i, filter in enumerate(DEMO_FILTERS):
                    self.create_result_inventories(org, i, filter)

            if options.get('proposals'):
                # warmup imports
                Inventory.objects.all()
                from awx.main.models import Group, Host

                Group.objects.all()[:20]
                Host.objects.all()[:20]
                # warmup runs
                host_pks = self.run_proposals(org, 1, '{{ "_" in inventory_hostname }}')
                del host_pks
                return
                host_pks = self.run_proposals(org, 2, '{{ notavar is defined }}')
                del host_pks
                # real scenarios
                host_pks = self.run_proposals(org, 1, '{{ "host_" in inventory_hostname }}')
                del host_pks
                host_pks = self.run_proposals(org, 2, '{{ host_marker is defined }}')
                del host_pks
                host_pks = self.run_proposals(org, 3, '{{ "flavor_4_" in group_names | join("") }}')
                del host_pks
                host_pks = self.run_proposals(org, 4, '{{ host_marker is defined }}')
                del host_pks
                host_pks = self.run_proposals(org, 5, '{{ "host_" in inventory_hostname }}')
                del host_pks

                # for i, template in enumerate(DEMO_TEMPLATES):
                #     self.run_proposals(org, i, template)

    def create_source_inventories(self, org):
        N_inventories = 5
        N_countries = 3
        N_regions = 3
        N_datacenters = 3
        N_hosts = 50

        groups_per_inv = N_countries * N_regions * N_datacenters
        total_groups = N_inventories * groups_per_inv
        total_hosts = N_hosts * total_groups
        print(f'Creating {N_inventories}, with tree structured groups, {total_hosts} hosts in total')

        start_time = time.time()

        for i in range(N_inventories):
            inv_name = f'smart_demo_{i}'
            existing_inv = Inventory.objects.filter(name=inv_name).first()
            if existing_inv:
                print(f'Deleting inventory {i}')
                delete_inventory(existing_inv.id, None)

            print(f'Creating the {i} inventory        {time.time() - start_time:.2f}')
            inv = Inventory.objects.create(name=inv_name, organization=org, variables=yaml.dump({'inventory_marker': f'inv_val_{i}'}))
            for j in range(N_countries):
                print(f'  {j} country                     {time.time() - start_time:.2f}')
                country = inv.groups.create(name=f'country_{j}', variables=yaml.dump({'country_marker': f'country_val_{j}'}))
                for k in range(N_regions):
                    print(f'    {k} region                    {time.time() - start_time:.2f}')
                    region = inv.groups.create(name=f'region_{k}_of_country_{j}', variables=yaml.dump({'region_marker': f'region_val_{k}'}))
                    country.children.add(region)
                    flavor_groups = [
                        inv.groups.create(name=f'flavor_{m}_of_region_{k}_country_{j}', variables=yaml.dump({'flavor_marker': f'flavor_val_{m}'}))
                        for m in range(N_hosts)
                    ]
                    region.children.add(*flavor_groups)
                    for l in range(N_datacenters):
                        dc = inv.groups.create(name=f'datacenter_{l}_of_region_{k}_of_country_{j}', variables=yaml.dump({'dc_marker': f'dc_val_{l}'}))
                        region.children.add(dc)
                        for m in range(N_hosts):
                            host = inv.hosts.create(
                                name=f'host_{m}_{l}_{k}_{j}_{i}',
                                variables=yaml.dump({'host_marker': f'host_val_{m}_{l}_{k}_{j}_{i}'})
                                # TODO: add ansible_facts
                            )
                            dc.hosts.add(host)
                            flavor_groups[m].hosts.add(host)

        print('')
        print(f'Total time taken for source inventory creation: {time.time() - start_time}')

    def create_result_inventories(self, org, i, filter):
        sm_name = f'smart_demo_result_{i}'
        existing_inv = Inventory.objects.filter(name=sm_name).first()
        if existing_inv:
            delete_inventory(existing_inv.id, None)
        sm = Inventory.objects.create(name=sm_name, organization=org, host_filter=filter, kind='smart')
        print('')
        print(f'Scenario {i}, pk={sm.id}, host_filter={sm.host_filter}')

        s = time.time()
        host_pks = list(sm.hosts.values_list('pk', flat=True))
        query_time = time.time() - s

        s = time.time()
        update_smart_memberships_for_inventory(sm)
        build_time = time.time() - s

        s = time.time()
        update_smart_memberships_for_inventory(sm)
        rebuild_time = time.time() - s

        s = time.time()
        sm.get_script_data()
        script_time = time.time() - s

        s = time.time()
        for host in sm.hosts.all():
            pass
        iterate_time = time.time() - s
        print(f'  host_ct={len(host_pks)}')
        print(f'  query_time={query_time} build_time={build_time} rebuild_time={rebuild_time}')
        print(f'  iterate_time={iterate_time} script_time={script_time}')

    @staticmethod
    def add_parents_recursive(running_id_list, group_id, parents_for_group):
        for parent_id in parents_for_group.get(group_id, []):
            if parent_id not in running_id_list:
                running_id_list.append(parent_id)
                running_id_list = Command.add_parents_recursive(running_id_list, parent_id, parents_for_group)
        return running_id_list

    def proposed_get_host_pks_from_inv(self, inv, template):
        host_pks = []

        group_data_from_id = {}
        for group in inv.groups.values('name', 'id', 'variables', 'inventory_id').iterator():
            group_data_from_id[group['id']] = group

        # Build in-memory mapping of groups and their children.
        parents_for_group = {}
        for from_group_id, to_group_id in Group.parents.through.objects.filter(to_group__inventory_id=inv.id).values_list('from_group_id', 'to_group_id'):
            parents_for_group.setdefault(from_group_id, []).append(to_group_id)

        # Build in-memory mapping of groups and their hosts.
        groups_for_host = {}
        for group_id, host_id in Group.hosts.through.objects.filter(host__inventory_id=inv.id).values_list('group_id', 'host_id'):
            groups_for_host.setdefault(host_id, []).append(group_id)

        inv_vars = parse_yaml_or_json(inv.variables)

        for host in inv.hosts.order_by('name').values('name', 'id', 'variables', 'inventory_id').iterator():
            hv = time.time()
            hostvars = inv_vars.copy()

            direct_group_ids = groups_for_host.get(host['id'], [])
            host_group_ids = Command.add_parents_recursive(direct_group_ids, group_id, parents_for_group)
            group_names = []
            for group_id in host_group_ids:
                group = group_data_from_id[group_id]
                if '_resolved_vars' not in group:
                    group['_resolved_vars'] = parse_yaml_or_json(group.pop('variables'))
                hostvars.update(group['_resolved_vars'])
                group_names.append(group['name'])

            hostvars.update(parse_yaml_or_json(host['variables']))
            # TODO: build out rest of "magic" variables relevant to this context
            hostvars['inventory_hostname'] = host['name']
            hostvars['group_names'] = group_names
            self.hostvars_time += time.time() - hv

            ts = time.time()
            sandbox_env = sandbox.ImmutableSandboxedEnvironment()
            sandbox_env.filters["bool"] = to_bool
            data = sandbox_env.from_string(template).render(**hostvars)
            self.template_time += time.time() - ts
            if to_bool(data):
                host_pks.append(host['id'])
        return host_pks

    def run_proposals(self, org, i, template):
        s = time.time()
        self.template_time = 0.0
        self.hostvars_time = 0.0

        host_pks = []
        # Loop over all normal (non-smart) inventories in the organization
        for inv in org.inventories.filter(kind=''):
            time.sleep(2)
            host_pks.extend(self.proposed_get_host_pks_from_inv(inv, template))

        print(f'Time taken in new proposal: {time.time() - s}')
        print(f'  discovered hosts: {len(host_pks)}')
        print(f'  time spent templating: {self.template_time}')
        print(f'  time spent combining hostvars: {self.hostvars_time}')
        return host_pks
