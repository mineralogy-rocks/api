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
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .utils import ErebusStorage
from .utils import _create_hash
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


class Unit(BaseModel, Nameable):
    class Meta:
        verbose_name = "Unit"
        verbose_name_plural = "Units"


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
    # TODO: add project/space field

    ALLOWED_EXTENSIONS = ["csv", "xls", "xlsx"]
    MAX_SIZE_ALLOWED = 1024 * 1024 * 10

    STATUS_QUEUED = 0
    STATUS_PARSED = 1
    STATUS_AI_REQUESTED = 2
    STATUS_AI_GENERATED = 3
    STATUS_PROCESSED = 4

    STATUS_PARSING_FAILED = 5
    STATUS_AI_FAILED = 6
    STATUS_PROCESSING_FAILED = 7

    STATUS_ARCHIVED = 8

    STATUS_CHOICES = (
        (STATUS_QUEUED, _("Queued")),
        (STATUS_PARSED, _("Parsed")),
        (STATUS_AI_REQUESTED, _("AI Requested")),
        (STATUS_AI_GENERATED, _("AI Response(s) Generated")),
        (STATUS_PROCESSED, _("Processed")),
        (STATUS_PARSING_FAILED, _("Parsing Failed")),
        (STATUS_AI_FAILED, _("AI Failed")),
        (STATUS_PROCESSING_FAILED, _("Processing Failed")),
        (STATUS_ARCHIVED, _("Archived")),
    )

    ACCESS_FULL_PUBLIC = 0
    ACCESS_SEMI_PUBLIC = 1
    ACCESS_PRIVATE = 2

    ACCESS_CHOICES = (
        (ACCESS_FULL_PUBLIC, _("Full Public")),
        (ACCESS_SEMI_PUBLIC, _("Semi Public")),
        (ACCESS_PRIVATE, _("Private")),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        help_text=_("Owner of the file"),
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
    markdown = models.TextField(null=True, blank=True)

    size = models.PositiveIntegerField(null=True, help_text=_("File size in bytes"))
    mime_type = models.CharField(max_length=200, null=True, blank=True, help_text=_("File MIME type"))

    status = models.IntegerField(
        choices=STATUS_CHOICES, default=STATUS_QUEUED, null=False, help_text=_("Processing status")
    )
    access = models.IntegerField(
        choices=ACCESS_CHOICES, default=ACCESS_FULL_PUBLIC, null=False, help_text=_("Access level")
    )

    parsed_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of parsing completion"))
    ai_generated_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of AI response generation"))
    processed_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of processing completion"))
    archived_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of archiving"))

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
        if self.status in [self.STATUS_PROCESSED, self.STATUS_PARSED] and self.chunks.exists():
            _max_version = self.chunks.aggregate(ver=models.Max("version"))["ver"]
            return default_storage.url(f"{self.uuid}/{_max_version}/parsed/")
        return None

    @property
    def parsing_version(self):
        if self.chunks:
            return self.chunks.order_by("-version").first().version
        return 0


class CodeVersion(BaseModel, Creatable):
    major = models.PositiveIntegerField(null=True)
    minor = models.PositiveIntegerField(null=True)
    patch = models.PositiveIntegerField(null=True)

    class Meta:
        verbose_name = "Code Version"
        verbose_name_plural = "Code Versions"
        get_latest_by = ["-created_at"]
        unique_together = ("major", "minor", "patch")
        ordering = ["-major", "-minor", "-patch"]

    @property
    def version(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    @version.setter
    def version(self, value):
        major, minor, patch = value.split(".")
        self.major = major
        self.minor = minor
        self.patch = patch


class Chunk(BaseModel, Creatable):
    hash = models.CharField(max_length=21, null=True, help_text=_("Hash of the chunk"))

    parent = models.ForeignKey(
        Queue, on_delete=models.CASCADE, null=False, related_name="chunks", help_text=_("Parent file of the chunk")
    )
    code_version = models.ForeignKey(
        CodeVersion, on_delete=models.SET_NULL, null=True, help_text=_("Code version used for processing")
    )
    version = models.IntegerField(default=1, help_text=_("Version of the chunk"))

    data = models.JSONField(null=True, help_text=_("Raw data from the chunk"))

    extract_composition = models.BooleanField(
        default=True, help_text=_("Flag to indicate if the chunk should be used for extracting composition")
    )
    extract_metadata = models.BooleanField(
        default=True, help_text=_("Flag to indicate if the chunk should be used for extracting metadata")
    )

    class Meta:
        verbose_name = "Chunk"
        verbose_name_plural = "Chunks"
        ordering = ["-created_at"]
        get_latest_by = ["-created_at"]

    def __str__(self):
        return self.hash

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = _create_hash(12)
        super().save(*args, **kwargs)


class ChunkIssue(BaseModel, Creatable):
    chunk = models.ForeignKey(Chunk, on_delete=models.CASCADE, null=False, related_name="issues")

    name = models.CharField(max_length=100, null=False, help_text=_("Issue name"))
    comment = models.TextField(null=False, help_text=_("Description"))

    email = models.EmailField(null=False, help_text=_("Email address of the reporter"))
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        help_text=_("User who reported the issue"),
    )

    is_resolved = models.BooleanField(default=False, help_text=_("Flag to indicate if the issue has been resolved"))
    resolved_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of resolution"))

    class Meta:
        verbose_name = "Chunk Issue"
        verbose_name_plural = "Chunk Issues"
        ordering = ["-created_at"]
        get_latest_by = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.is_resolved:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)


class PromptTag(BaseModel):
    key = models.CharField(max_length=200, null=False, unique=True)
    value = models.CharField(max_length=200, null=False)

    class Meta:
        verbose_name = "Prompt Tag"
        verbose_name_plural = "Prompt Tags"


class PromptType(BaseModel, Nameable):
    tags = models.ManyToManyField(PromptTag)

    class Meta:
        verbose_name = "Prompt Tag"
        verbose_name_plural = "Prompt Tags"


class Prompt(BaseModel, Creatable):
    openai_id = models.CharField(max_length=255, null=True)

    text = models.TextField(blank=True, null=True)
    type = models.ForeignKey(PromptType, null=True, on_delete=models.SET_NULL, related_name="prompts")

    class Meta:
        verbose_name = "Prompt"
        verbose_name_plural = "Prompts"
        ordering = ["-created_at"]
        get_latest_by = ["-created_at"]


class AIResponse(BaseModel, Creatable):
    MODEL_GPT_5_NANO = "gpt-5-nano"
    MODEL_GPT_5_MINI = "gpt-5-mini-2025-08-07"

    MODEL_CHOICES = (
        (MODEL_GPT_5_NANO, _("GPT-5 Nano")),
        (MODEL_GPT_5_MINI, _("GPT-5 Mini")),
    )

    hash = models.CharField(max_length=21, null=True, help_text=_("Hash of the chunk"))

    batch = models.CharField(max_length=255, null=True, help_text=_("Batch identifier for processing"))
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, null=False, related_name="responses")
    prompt = models.ForeignKey(Prompt, on_delete=models.SET_NULL, null=True, related_name="responses")
    model = models.CharField(choices=MODEL_CHOICES, null=False, help_text=_("Model used for processing"))

    request_raw = models.TextField(null=True, blank=True, help_text=_("Prompt text used for response generation"))
    response_raw = models.TextField(null=True, blank=True, help_text=_("Raw response text from AI service"))
    response_parsed = models.JSONField(null=True, blank=True, help_text=_("Parsed response from AI service"))

    is_error = models.BooleanField(default=False, help_text=_("Flag to indicate if processing/extraction failed"))
    exception = models.TextField(null=True, blank=True, help_text=_("Exception message"))

    scheduled_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of response generation"))
    answered_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of response generation"))
    processed_at = models.DateTimeField(null=True, blank=True, help_text=_("Datetime of processing completion"))

    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)

    chunks = models.ManyToManyField(Chunk, through="AIResponseChunk", related_name="ai_responses")

    class Meta:
        verbose_name = "AI Response"
        verbose_name_plural = "AI Responses"
        ordering = ["-created_at"]
        get_latest_by = ["-created_at"]

    def __str__(self):
        return self.hash

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = _create_hash(12)
        super().save(*args, **kwargs)


class AIResponseChunk(BaseModel):
    ai_response = models.ForeignKey(
        AIResponse,
        on_delete=models.CASCADE,
        null=False,
        related_name="chunk_associations",
        help_text=_("AI response"),
    )
    chunk = models.ForeignKey(
        Chunk,
        on_delete=models.CASCADE,
        null=False,
        related_name="response_associations",
        help_text=_("Chunk used in AI response"),
    )

    class Meta:
        verbose_name = "AI Response Chunk"
        verbose_name_plural = "AI Response Chunks"
        ordering = [
            "-id",
        ]
        unique_together = ["ai_response", "chunk"]
