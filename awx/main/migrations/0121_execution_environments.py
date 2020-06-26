# Generated by Django 2.2.11 on 2020-07-08 18:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0003_taggeditem_add_unique_index'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('main', '0120_galaxy_credentials'),
    ]

    operations = [
        migrations.AddField(
            model_name='unifiedjob',
            name='pull',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='unifiedjobtemplate',
            name='pull',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='ExecutionEnvironment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=None, editable=False)),
                ('modified', models.DateTimeField(default=None, editable=False)),
                ('description', models.TextField(blank=True, default='')),
                ('image', models.CharField(help_text='The registry location where the container is stored.', max_length=1024, verbose_name='image location')),
                ('managed_by_tower', models.BooleanField(default=False, editable=False)),
                ('created_by', models.ForeignKey(default=None, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="{'class': 'executionenvironment', 'model_name': 'executionenvironment', 'app_label': 'main'}(class)s_created+", to=settings.AUTH_USER_MODEL)),
                ('credential', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='executionenvironments', to='main.Credential')),
                ('modified_by', models.ForeignKey(default=None, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="{'class': 'executionenvironment', 'model_name': 'executionenvironment', 'app_label': 'main'}(class)s_modified+", to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(blank=True, default=None, help_text='The organization used to determine access to this execution environment.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='executionenvironments', to='main.Organization')),
                ('tags', taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags')),
            ],
            options={
                'ordering': (django.db.models.expressions.OrderBy(django.db.models.expressions.F('organization_id'), nulls_first=True), 'image'),
                'unique_together': {('organization', 'image')},
            },
        ),
        migrations.AddField(
            model_name='activitystream',
            name='execution_environment',
            field=models.ManyToManyField(blank=True, to='main.ExecutionEnvironment'),
        ),
        migrations.AddField(
            model_name='organization',
            name='default_environment',
            field=models.ForeignKey(blank=True, default=None, help_text='The default execution environment for jobs run by this organization.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='main.ExecutionEnvironment'),
        ),
        migrations.AddField(
            model_name='unifiedjob',
            name='execution_environment',
            field=models.ForeignKey(blank=True, default=None, help_text='The container image to be used for execution.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='unifiedjobs', to='main.ExecutionEnvironment'),
        ),
        migrations.AddField(
            model_name='unifiedjobtemplate',
            name='execution_environment',
            field=models.ForeignKey(blank=True, default=None, help_text='The container image to be used for execution.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='unifiedjobtemplates', to='main.ExecutionEnvironment'),
        ),
    ]
