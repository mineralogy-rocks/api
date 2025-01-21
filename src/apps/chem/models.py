# -*- coding: UTF-8 -*-
from core.models.base import BaseModel
from core.models.base import Creatable
from core.models.base import Nameable
from core.models.mineral import Mineral
from django.db import models


class Component(BaseModel, Nameable):
    is_major = models.BooleanField(
        null=False,
        default=False,
    )

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

    external_key = models.CharField(max_length=200, null=False, unique=True)
    mineral = models.ForeignKey(
        Mineral,
        on_delete=models.CASCADE,
        related_name="measurements",
        default=None,
    )
    mineral_note = models.TextField(
        null=True,
        blank=True,
    )
    resource = models.IntegerField(
        choices=RESOURCE_CHOICES,
        null=False,
    )
    sample_name = models.CharField(
        max_length=200,
        null=False,
    )
    grain_size = models.CharField(
        max_length=200,
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
    is_primary = models.BooleanField(null=False, default=False)
    tectonic_setting = models.IntegerField(
        choices=TECTONIC_SETTING_CHOICES,
        null=True,
        default=None,
    )
    citation = models.TextField(blank=True, null=True)

    latitude_min = models.FloatField(null=True, default=None)
    latitude_max = models.FloatField(null=True, default=None)
    longitude_min = models.FloatField(null=True, default=None)
    longitude_max = models.FloatField(null=True, default=None)
    elevation_min = models.FloatField(null=True, default=None)
    elevation_max = models.FloatField(null=True, default=None)

    location = models.CharField(max_length=350, null=True, default=None)
    location_note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Measurement"
        verbose_name_plural = "Measurements"


class MeasurementComponent(BaseModel):
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
