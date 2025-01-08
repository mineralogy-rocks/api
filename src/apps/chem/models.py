# -*- coding: UTF-8 -*-
from core.models.base import BaseModel
from core.models.base import Creatable
from core.models.base import Nameable
from core.models.mineral import Mineral
from django.db import models


class Component(BaseModel, Nameable):
    class Meta:
        ordering = [
            "name",
        ]
        verbose_name = "Component"
        verbose_name_plural = "Components"


class Measurement(BaseModel, Creatable):
    ALTERATION_CHOICES = (
        (1, "Almost totally altered"),
        (2, "Extensively altered"),
        (3, "Fresh"),
        (4, "Moderately altered"),
        (5, "Slightly altered"),
    )

    PRIMARY_SECONDARY_CHOICES = (
        (1, "Primary"),
        (2, "Secondary"),
    )

    TECTONIC_SETTING_CHOICES = (
        (1, "Archean Craton (including Greenstone Belts)"),
        (2, "Complex Volcanic Settings"),
        (3, "Continental Flood Basalt"),
        (4, "Convergent Margin"),
        (5, "Intraplate Volcanics"),
        (6, "Ocean Island"),
        (7, "Ocean-basin Flood Basalt"),
        (8, "Oceanic Plateau"),
        (9, "Rift Volcanics"),
        (10, "Seamount"),
        (11, "Submarine Ridge"),
    )

    RESOURCE_CHOICES = ((1, "DIGIS"),)

    key = models.CharField(max_length=200, null=False, unique=True)
    mineral = models.ForeignKey(
        Mineral,
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    resource = models.IntegerField(
        choices=RESOURCE_CHOICES,
        null=False,
    )
    sample_name = models.CharField(
        max_length=200,
        null=False,
    )
    grain_size = models.TextField(
        null=True,
        default=None,
    )
    rock_name = models.CharField(
        max_length=200,
        null=True,
        default=None,
    )
    rock_texture = models.TextField(
        null=True,
        default=None,
    )
    alteration = models.IntegerField(
        choices=ALTERATION_CHOICES,
        null=True,
        default=None,
    )
    primary_secondary = models.IntegerField(
        choices=PRIMARY_SECONDARY_CHOICES,
        null=True,
        default=None,
    )
    tectonic_setting = models.IntegerField(
        choices=TECTONIC_SETTING_CHOICES,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = "Measurement"
        verbose_name_plural = "Measurements"


class MeasurementComponents(BaseModel):
    UNIT_CHOICES = (
        (1, "ppm"),
        (2, "ppb"),
        (3, "ppt"),
        (4, "wt%)"),
    )

    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.CASCADE,
        related_name="components",
    )
    component = models.ForeignKey(
        Component,
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    value = models.FloatField(
        null=False,
    )
    unit = models.IntegerField(
        choices=UNIT_CHOICES,
        null=False,
    )

    class Meta:
        unique_together = [
            "measurement",
            "component",
        ]
        verbose_name = "Measurement Component"
        verbose_name_plural = "Measurement Components"
