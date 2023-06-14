# Generated by Django 4.2.1 on 2023-06-05 23:47

import django.db.models.deletion
from django.db import migrations, models

import tests.app.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestModel",
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
                ("booleanfield", models.BooleanField(blank=True, null=True)),
                ("textfield", models.TextField(blank=True, null=True)),
                ("charfield", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "emailfield",
                    models.EmailField(blank=True, max_length=254, null=True),
                ),
                ("slugfield", models.SlugField(blank=True, null=True)),
                ("urlfield", models.URLField(blank=True, null=True)),
                ("filefield", models.FileField(blank=True, null=True, upload_to="")),
                ("filepathfield", models.FilePathField(blank=True, null=True)),
                (
                    "decimalfield",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=14, null=True
                    ),
                ),
                ("floatfield", models.FloatField(blank=True, null=True)),
                ("bigintegerfield", models.BigIntegerField(blank=True, null=True)),
                ("integerfield", models.IntegerField(blank=True, null=True)),
                (
                    "positivebigintegerfield",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                ("smallintegerfield", models.SmallIntegerField(blank=True, null=True)),
                (
                    "positivesmallintegerfield",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "positiveintegerfield",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("datefield", models.DateField(blank=True, null=True)),
                ("datetimefield", models.DateTimeField(blank=True, null=True)),
                ("durationfield", models.DurationField(blank=True, null=True)),
                ("timefield", models.TimeField(blank=True, null=True)),
                ("binaryfield", models.BinaryField(blank=True, null=True)),
                ("uuidfield", models.UUIDField(blank=True, null=True)),
                (
                    "genericipaddressfield",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("jsonfield", models.JSONField(blank=True, null=True)),
                (
                    "json",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=tests.app.models.JSONEncoder,
                        null=True,
                    ),
                ),
                (
                    "foreignkey",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="foreignkey_reverse",
                        to="app.testmodel",
                    ),
                ),
                (
                    "manytomanyfield",
                    models.ManyToManyField(blank=True, to="app.testmodel"),
                ),
                (
                    "onetoonefield",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="onetoonefield_reverse",
                        to="app.testmodel",
                    ),
                ),
            ],
            options={
                "verbose_name": "Field Implementation",
            },
        ),
    ]
