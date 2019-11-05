from django.core.management.base import BaseCommand, CommandError

from awx.main.models import Job

# to run this you need
# pip install graphviz

# example use
# awx-manage inspect_job --job=230 --file=alan

# important things
# 'changed': False,
# 'counter': 7,
# 'event': 'playbook_on_start',
# 'failed': False,
# 'host_name': '',
# 'id': 1274,
# 'parent_uuid': '',
# 'play': '',
# 'role': '',
# 'stdout': '',
# 'uuid': 'd6e95af9-69a7-4540-b41e-70e3044db7a2',
# 'verbosity': 0


def pretty_event(event):
    # r = {}
    # for field in ('event', 'counter', 'host_name', 'changed', 'play', 'role'):
    #     v = getattr(event, field)
    #     if v:
    #         r[field] = v
    # strs = ['{}={}'.format(k, v) for k, v in r.items()]
    # return ' '.join(strs)
    return '{} {}'.format(event.event, event.counter)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--job', dest='job', type=int, default=None,
                            help='The job to inspect.')
        parser.add_argument('--file', dest='file', type=str, default='output',
                            help='Where to write file to (do not include extension)')
        parser.add_argument('--ext', dest='ext', type=str, default='png',
                            help='Extension')

    def handle(self, **options):
        job_id = int(options['job'])
        file = options['file']

        try:
            from graphviz import Digraph
        except ModuleNotFoundError as e:
            raise CommandError('You need graphviz to run this command, `pip install graphviz` {}'.format(e))

        dot = Digraph(
            format=options['ext'],
            comment='Event structure for job={}'.format(job_id)
        )
        dot.graph_attr['rankdir'] = 'LR'

        job = Job.objects.prefetch_related('job_events').get(pk=job_id)

        uuid_map = {}
        for event in job.job_events.all():
            if event.uuid:
                uuid_map[event.uuid] = event

        edges = []
        nodes = []

        print('Will run against {} events'.format(job.job_events.count()))

        for event in job.job_events.all():
            if event.event == 'verbose':
                continue
            if event.event == 'runner_on_start':
                continue
            nodes.append(pretty_event(event))
            if event.parent_uuid:
                parent = uuid_map[event.parent_uuid]
                edges.append(
                    (pretty_event(event), pretty_event(parent))
                )

        print('Graph is prepared, running graphviz stuff')

        for node in nodes:
            dot.node(node, node)
        for r, p in edges:
            dot.edge(r, p)

        print(dot.source)
        dot.render(file, view=False)
