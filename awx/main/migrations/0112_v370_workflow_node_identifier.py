# Generated by Django 2.2.8 on 2020-03-14 02:29

from django.db import migrations, models
import uuid
import logging


logger = logging.getLogger('awx.main.migrations')


def create_uuid(apps, schema_editor):
    WorkflowJobTemplateNode = apps.get_model('main', 'WorkflowJobTemplateNode')
    ct = 0
    for node in WorkflowJobTemplateNode.objects.iterator():
        node.identifier = uuid.uuid4()
        node.save(update_fields=['identifier'])
        ct += 1
    if ct:
        logger.info(f'Automatically created uuid4 identifier for {ct} workflow nodes')


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0099_v361_license_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowjobnode',
            name='identifier',
            field=models.CharField(blank=True, help_text='An identifier coresponding to the workflow job template node that this node was created from.', max_length=512),
        ),
        migrations.AddField(
            model_name='workflowjobtemplatenode',
            name='identifier',
            field=models.CharField(blank=True, null=True, help_text='An identifier for this node that is unique within its workflow. It is copied to workflow job nodes corresponding to this node.', max_length=512),
        ),
        migrations.RunPython(create_uuid, migrations.RunPython.noop),  # this fixes the uuid4 issue
        migrations.AlterField(
            model_name='workflowjobtemplatenode',
            name='identifier',
            field=models.CharField(default=uuid.uuid4, help_text='An identifier for this node that is unique within its workflow. It is copied to workflow job nodes corresponding to this node.', max_length=512),
        ),
        migrations.AlterUniqueTogether(
            name='workflowjobtemplatenode',
            unique_together={('identifier', 'workflow_job_template')},
        ),
        migrations.AddIndex(
            model_name='workflowjobnode',
            index=models.Index(fields=['identifier', 'workflow_job'], name='main_workfl_identif_87b752_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowjobnode',
            index=models.Index(fields=['identifier'], name='main_workfl_identif_efdfe8_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowjobtemplatenode',
            index=models.Index(fields=['identifier'], name='main_workfl_identif_0cc025_idx'),
        ),
    ]
