from django.core.management.base import BaseCommand, CommandError

from awx.main.models import Role

# to run this you need
# pip install graphviz

# example use
# awx-manage inspect_role --role=10786 --file=testing/out


def format_role(role):
    return '{}-{}-{}'.format(
        getattr(role.content_type, 'model', None),
        role.role_field,
        role.pk
    )


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--role', dest='role', type=int, default=None,
                            help='The role to inspect.')
        parser.add_argument('--file', dest='file', type=str, default='output',
                            help='Where to write file to (do not include extension)')
        parser.add_argument('--method', dest='method', type=str, default='up',
                            choices=['up', 'down', 'downup'],
                            help='What directions to crawl to find the graph nodes.')
        parser.add_argument('--ext', dest='ext', type=str, default='png',
                            help='Extension')

    def handle(self, **options):
        role_pk = int(options['role'])
        file = options['file']
        method = options['method']
        try:
            from graphviz import Digraph
        except ModuleNotFoundError as e:
            raise CommandError('You need graphviz to run this command, `pip install graphviz` {}'.format(e))

        dot = Digraph(
            format=options['ext'],
            comment='Ancestry structure for role={}'.format(role_pk)
        )
        dot.graph_attr['rankdir'] = 'LR'

        role = Role.objects.prefetch_related(
            'ancestors__content_type', 'parents',
            'ancestors__parents'
        ).get(pk=role_pk)
        edges = []
        nodes = []

        if method == 'up':
            nodes_qs = role.ancestors.all()
        elif method == 'down':
            nodes_qs = role.descendents.all()
        else:  # down-up
            # similar to visible roles
            nodes_qs = Role.objects.filter(
                # ancestors__descendents=role
                descendents__ancestors=role
            )

        print('Will run against {} nodes'.format(nodes_qs.count()))

        for r in nodes_qs.distinct():
            nodes.append(format_role(r))
            for p in r.parents.all():
                edges.append(
                    (format_role(r), format_role(p))
                )

        for node in nodes:
            dot.node(node, node)
        for r, p in edges:
            dot.edge(r, p)

        print(dot.source)
        dot.render(file, view=False)
