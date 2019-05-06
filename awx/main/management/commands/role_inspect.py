from django.core.management.base import BaseCommand

from awx.main.tasks import profile_sql

from awx.main.models import *


def format_role(role):
    return '{}-{}-{}'.format(
        getattr(role.content_type, 'model', None),
        role.role_field,
        role.pk
    )


class Command(BaseCommand):
    """
    Enable or disable SQL Profiling across all Python processes.
    SQL profile data will be recorded at /var/log/tower/profile
    """

    def add_arguments(self, parser):
        parser.add_argument('--role', dest='role', type=int, default=None,
                            help='The role to inspect.')
        parser.add_argument('--file', dest='file', type=str, default='output',
                            help='Where to write file to')

    def handle(self, **options):
        role_pk = int(options['role'])
        file = options['file']
        from graphviz import Digraph

        dot = Digraph(format='png')

        role = Role.objects.prefetch_related(
            'ancestors__content_type', 'parents',
            'ancestors__parents'
        ).get(pk=role_pk)
        edges = []
        nodes = []
        for r in role.ancestors.all():
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
