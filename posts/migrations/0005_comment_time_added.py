# Generated by Django 5.1.1 on 2024-10-22 19:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_alter_post_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='time_added',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
