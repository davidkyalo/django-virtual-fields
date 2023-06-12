# Generated by Django 4.2.1 on 2023-06-06 00:20

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import examples.example_01.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("dob", models.DateField(verbose_name="date of birth")),
                (
                    "data",
                    models.JSONField(
                        blank=True,
                        default=examples.example_01.models._fake_data,
                        encoder=examples.example_01.models.JSONEncoder,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                (
                    "type",
                    models.CharField(
                        choices=[("article", "Article"), ("comment", "Comment")],
                        max_length=32,
                    ),
                ),
                (
                    "published_at",
                    models.DateTimeField(default=django.utils.timezone.now, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "data",
                    models.JSONField(
                        default=dict, encoder=examples.example_01.models.JSONEncoder
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="posts",
                        to="example_01.person",
                    ),
                ),
                (
                    "likes",
                    models.ManyToManyField(
                        related_name="liked", to="example_01.person"
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="example_01.post",
                    ),
                ),
            ],
            options={
                "default_manager_name": "objects",
            },
        ),
        migrations.CreateModel(
            name="Article",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("example_01.post",),
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("example_01.post",),
        ),
    ]
