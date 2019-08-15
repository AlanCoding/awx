# Generated by Django 2.2.2 on 2019-07-23 17:56

import awx.main.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0083_v360_job_branch_overrirde'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowjobtemplate',
            name='ask_limit_on_launch',
            field=awx.main.fields.AskForField(blank=True, default=False),
        ),
        migrations.AddField(
            model_name='workflowjobtemplate',
            name='ask_scm_branch_on_launch',
            field=awx.main.fields.AskForField(blank=True, default=False),
        ),
        migrations.AddField(
            model_name='workflowjobtemplate',
            name='char_prompts',
            field=awx.main.fields.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='joblaunchconfig',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='joblaunchconfigs', to='main.Inventory'),
        ),
        migrations.AlterField(
            model_name='schedule',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='schedules', to='main.Inventory'),
        ),
        migrations.AlterField(
            model_name='workflowjob',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='workflowjobs', to='main.Inventory'),
        ),
        migrations.AlterField(
            model_name='workflowjobnode',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='workflowjobnodes', to='main.Inventory'),
        ),
        migrations.AlterField(
            model_name='workflowjobtemplate',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='workflowjobtemplates', to='main.Inventory'),
        ),
        migrations.AlterField(
            model_name='workflowjobtemplatenode',
            name='inventory',
            field=models.ForeignKey(blank=True, default=None, help_text='Inventory applied as a prompt, assuming job template prompts for inventory', null=True, on_delete=models.deletion.SET_NULL, related_name='workflowjobtemplatenodes', to='main.Inventory'),
        ),
    ]
