# -*- coding: UTF-8 -*-
import uuid
from decimal import Decimal

from core.models.base import Creatable
from core.models.base import Updatable
from core.utils import unique_slugify
from django.apps import apps
from django.core.validators import RegexValidator
from django.db import models


class StoneColor(Creatable, Updatable):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    hex = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r"^#[0-9a-fA-F]{6}$")],
    )

    class Meta:
        ordering = ["name"]

        verbose_name = "Stone color"
        verbose_name_plural = "Stone colors"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class StoneCut(Creatable, Updatable):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

        verbose_name = "Stone cut"
        verbose_name_plural = "Stone cuts"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class StoneTreatment(Creatable, Updatable):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

        verbose_name = "Stone treatment"
        verbose_name_plural = "Stone treatments"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Stone(Creatable, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    mineral = models.CharField(max_length=100, null=True, blank=True)
    item_number = models.CharField(max_length=100, null=True, blank=True)
    color = models.ForeignKey(
        StoneColor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stones",
    )
    cut = models.ForeignKey(
        StoneCut,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stones",
    )
    treatment = models.ForeignKey(
        StoneTreatment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stones",
    )
    weight_carats = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=200, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    price_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    shipment_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    shipment_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vat_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vat_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gross_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gross_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    adjusted_price_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    adjusted_price_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sold_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_sold = models.BooleanField(default=False)
    is_selling = models.BooleanField(default=False)
    sold_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "Stone"
        verbose_name_plural = "Stones"

    def __str__(self):
        return self.name

    def _compute_gross(self):
        for cur in ("usd", "eur"):
            parts = [getattr(self, f"{p}_{cur}") for p in ("price", "shipment", "vat")]
            present = [Decimal(str(p)) for p in parts if p is not None]
            setattr(self, f"gross_{cur}", sum(present) if present else None)

    def save(self, *args, **kwargs):
        self._compute_gross()
        super().save(*args, **kwargs)

    @property
    def has_report(self):
        try:
            Report = apps.get_model("store", "Report")
        except LookupError:
            return False
        return Report.objects.filter(linked_stone_id=self.id).exists()


class StoneImage(Creatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stone = models.ForeignKey(Stone, on_delete=models.CASCADE, related_name="images")
    image_url = models.CharField(max_length=1024)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

        verbose_name = "Stone image"
        verbose_name_plural = "Stone images"

    def __str__(self):
        return f"{self.stone_id} #{self.display_order}"


class Report(Creatable, Updatable):
    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"
    CURRENCY_UAH = "UAH"
    CURRENCY_CHOICES = (
        (CURRENCY_USD, "USD"),
        (CURRENCY_EUR, "EUR"),
        (CURRENCY_UAH, "UAH"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=255)
    stone = models.CharField(max_length=200, null=True, blank=True)
    linked_stone = models.OneToOneField(
        Stone,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="report",
    )
    description = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    owner = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gem_reports",
    )
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    owner_email = models.EmailField(null=True, blank=True)
    owner_telephone = models.CharField(max_length=50, null=True, blank=True)

    public = models.BooleanField(default=False)

    shape_cutting_style = models.CharField(max_length=255, null=True, blank=True)
    measurements = models.CharField(max_length=255, null=True, blank=True)
    carat_weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    specific_gravity = models.CharField(max_length=255, null=True, blank=True)
    refractive_index = models.CharField(max_length=255, null=True, blank=True)
    double_refraction = models.CharField(max_length=255, null=True, blank=True)
    polariscope = models.CharField(max_length=255, null=True, blank=True)
    pleochroism = models.CharField(max_length=255, null=True, blank=True)
    chelsea_color_filter = models.CharField(max_length=255, null=True, blank=True)
    fluorescence_sw = models.CharField(max_length=255, null=True, blank=True)
    fluorescence_lw = models.CharField(max_length=255, null=True, blank=True)
    microscope = models.TextField(null=True, blank=True)
    treatment = models.CharField(max_length=255, null=True, blank=True)
    origin = models.CharField(max_length=255, null=True, blank=True)

    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self):
        return self.title

    def resolve_owner(self):
        if not self.owner_email:
            self.owner = None
            return
        User = apps.get_model("users", "User")
        self.owner = User.objects.filter(email__iexact=self.owner_email).first()

    def save(self, *args, **kwargs):
        self.resolve_owner()
        super().save(*args, **kwargs)


class ReportImage(Creatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="images")
    image_url = models.CharField(max_length=1024)
    title = models.CharField(max_length=255, null=True, blank=True)
    caption = models.TextField(null=True, blank=True)
    is_headline = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

        verbose_name = "Report image"
        verbose_name_plural = "Report images"

    def __str__(self):
        return f"{self.report_id} #{self.display_order}"
