# -*- coding: UTF-8 -*-
from django.db import migrations

DEFAULT_CHANNELS = [
    ("mineralogy.rocks", "mineralogy.rocks"),
    ("gemsla.be", "gemsla.be"),
]
DEFAULT_CHANNEL_SLUG = "mineralogy.rocks"


def seed_channels(apps, schema_editor):
    Channel = apps.get_model("blog", "Channel")
    Post = apps.get_model("blog", "Post")

    channels = {}
    for name, slug in DEFAULT_CHANNELS:
        channel, _ = Channel.objects.get_or_create(slug=slug, defaults={"name": name})
        channels[slug] = channel

    default_channel = channels[DEFAULT_CHANNEL_SLUG]
    for post in Post.objects.all():
        post.channels.add(default_channel)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0005_channel_post_content_json_post_cover_image_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_channels, noop),
    ]
