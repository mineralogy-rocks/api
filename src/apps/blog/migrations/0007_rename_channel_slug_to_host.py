# -*- coding: UTF-8 -*-
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0006_seed_channels"),
    ]

    operations = [
        migrations.RenameField(
            model_name="channel",
            old_name="slug",
            new_name="host",
        ),
    ]
