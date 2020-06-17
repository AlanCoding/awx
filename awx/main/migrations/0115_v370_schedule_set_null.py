# Generated by Django 2.2.11 on 2020-05-04 02:26

import awx.main.utils.polymorphic
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0099_v361_license_cleanup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unifiedjob',
            name='schedule',
            field=models.ForeignKey(default=None, editable=False, null=True, on_delete=awx.main.utils.polymorphic.SET_NULL, to='main.Schedule'),
        ),
        migrations.AlterField(
            model_name='unifiedjobtemplate',
            name='next_schedule',
            field=models.ForeignKey(default=None, editable=False, null=True, on_delete=awx.main.utils.polymorphic.SET_NULL, related_name='unifiedjobtemplate_as_next_schedule+', to='main.Schedule'),
        ),
    ]
