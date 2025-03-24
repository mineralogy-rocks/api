# -*- coding: UTF-8 -*-
import mimetypes
import uuid

from core.models.base import BaseModel
from core.models.base import Creatable
from core.models.base import Nameable
from core.models.base import Updatable
from core.models.mineral import Mineral
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import models
from django.utils.translation import gettext_lazy as _

from .utils import ErebusStorage
from .utils import _get_parsed_path
from .utils import _get_upload_path


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

    RESOURCE_CHOICES = ((1, "DIGIS"), (2, "EREBUS"))

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
        (4, "wt)"),
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


class Queue(BaseModel, Creatable, Updatable):
    ALLOWED_EXTENSIONS = ["csv", "xls", "xlsx"]
    MAX_SIZE_ALLOWED = 1024 * 1024 * 10

    STATUS_QUEUED = 0
    STATUS_PARSED = 1
    STATUS_PROCESSED = 2
    STATUS_FAILED = 3
    STATUS_ARCHIVED = 4

    STATUS_CHOICES = (
        (STATUS_QUEUED, _("Queued")),
        (STATUS_PARSED, _("Parsed")),
        (STATUS_PROCESSED, _("Processed")),
        (STATUS_FAILED, _("Failed")),
        (STATUS_ARCHIVED, _("Archived")),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        help_text=_("User who uploaded the file"),
    )

    name = models.CharField(max_length=1000, null=False, help_text=_("File name"))
    description = models.TextField(null=True, blank=True, help_text=_("Description of the file"))

    file = models.FileField(
        upload_to=_get_upload_path,
        storage=ErebusStorage(),
        max_length=1000,
        null=False,
        help_text=_("File stored in S3"),
    )

    size = models.PositiveIntegerField(null=True, help_text=_("File size in bytes"))
    mime_type = models.CharField(max_length=200, null=True, blank=True, help_text=_("File MIME type"))

    status = models.IntegerField(
        choices=STATUS_CHOICES, default=STATUS_QUEUED, null=False, help_text=_("Processing status")
    )

    parsed_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of parsing completion"))
    processed_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of processing completion"))

    class Meta:
        verbose_name = "File Queue"
        verbose_name_plural = "File Queues"
        ordering = ["-created_at", "-updated_at"]

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"

    def get_absolute_url(self):
        return self.file.url

    def save(self, *args, **kwargs):
        try:
            self.mime_type = mimetypes.guess_type(self.file.name)[0]
        except Exception:
            pass
        self.size = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.status = self.STATUS_ARCHIVED
        self.save()
        return self

    @property
    def get_unprocessed_url(self):
        return default_storage.url(f"{self.uuid}/unprocessed/")

    @property
    def get_parsed_url(self):
        if self.status in [self.STATUS_PROCESSED, self.STATUS_PARSED]:
            return default_storage.url(f"{self.uuid}/parsed/")
        return None

    @property
    def get_chunks(self):
        return self.chunks.filter(is_processed=False)


class Chunk(BaseModel, Creatable, Updatable):
    name = models.CharField(max_length=1000, null=False, help_text=_("Chunk name"))

    parent = models.ForeignKey(
        Queue, on_delete=models.CASCADE, null=False, related_name="chunks", help_text=_("Parent file of the chunk")
    )
    chunk = models.FileField(
        upload_to=_get_parsed_path,
        storage=ErebusStorage(),
        max_length=1000,
        null=False,
        help_text=_("File chunk stored in S3"),
    )

    response = models.TextField(null=True, blank=True, help_text=_("Raw response from AI service"))
    clean_response = models.JSONField(null=True, blank=True, help_text=_("Parsed response from AI service"))

    is_processed = models.BooleanField(default=False, help_text=_("Flag to indicate if processing is over"))
    is_error = models.BooleanField(default=False, help_text=_("Flag to indicate if processing failed"))

    class Meta:
        verbose_name = "Chunk"
        verbose_name_plural = "Chunks"
        ordering = ["-created_at", "-updated_at"]
        get_latest_by = ["-created_at"]

    def __str__(self):
        return self.name
