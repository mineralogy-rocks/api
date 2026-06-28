# -*- coding: UTF-8 -*-
from rest_framework import serializers

from .models import Report
from .models import ReportImage
from .models import Stone
from .models import StoneColor
from .models import StoneCut
from .models import StoneImage
from .models import StoneTreatment
from .storage import public_url
from .storage import signed_url


class StoneColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoneColor
        fields = [
            "id",
            "name",
            "slug",
            "hex",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class StoneCutSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoneCut
        fields = [
            "id",
            "name",
            "slug",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class StoneTreatmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoneTreatment
        fields = [
            "id",
            "name",
            "slug",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class StoneImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoneImage
        fields = [
            "id",
            "image_url",
            "display_order",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {"display_order": {"required": False}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["image_url"] = public_url(instance.image_url)
        return data


class StonePublicListSerializer(serializers.ModelSerializer):
    color = StoneColorSerializer(read_only=True)
    cut = StoneCutSerializer(read_only=True)
    treatment = StoneTreatmentSerializer(read_only=True)
    images = StoneImageSerializer(many=True, read_only=True)

    class Meta:
        model = Stone
        fields = [
            "id",
            "name",
            "mineral",
            "item_number",
            "color",
            "cut",
            "treatment",
            "weight_carats",
            "dimensions",
            "country",
            "description",
            "selling_price",
            "sold_price",
            "sold_at",
            "is_sold",
            "is_selling",
            "created_at",
            "images",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")
        return queryset.select_related("color", "cut", "treatment").prefetch_related("images")


class StonePublicDetailSerializer(StonePublicListSerializer):
    has_report = serializers.ReadOnlyField()

    class Meta(StonePublicListSerializer.Meta):
        fields = StonePublicListSerializer.Meta.fields + ["has_report"]


class StoneAdminSerializer(serializers.ModelSerializer):
    color = StoneColorSerializer(read_only=True)
    cut = StoneCutSerializer(read_only=True)
    treatment = StoneTreatmentSerializer(read_only=True)
    color_id = serializers.PrimaryKeyRelatedField(
        queryset=StoneColor.objects.all(),
        source="color",
        write_only=True,
        required=False,
        allow_null=True,
    )
    cut_id = serializers.PrimaryKeyRelatedField(
        queryset=StoneCut.objects.all(),
        source="cut",
        write_only=True,
        required=False,
        allow_null=True,
    )
    treatment_id = serializers.PrimaryKeyRelatedField(
        queryset=StoneTreatment.objects.all(),
        source="treatment",
        write_only=True,
        required=False,
        allow_null=True,
    )
    images = StoneImageSerializer(many=True, required=False)
    has_report = serializers.ReadOnlyField()

    class Meta:
        model = Stone
        fields = [
            "id",
            "name",
            "description",
            "mineral",
            "item_number",
            "color",
            "cut",
            "treatment",
            "color_id",
            "cut_id",
            "treatment_id",
            "weight_carats",
            "dimensions",
            "country",
            "price_usd",
            "price_eur",
            "shipment_usd",
            "shipment_eur",
            "vat_usd",
            "vat_eur",
            "gross_usd",
            "gross_eur",
            "adjusted_price_eur",
            "adjusted_price_usd",
            "selling_price",
            "sold_price",
            "is_sold",
            "is_selling",
            "sold_at",
            "notes",
            "has_report",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gross_usd",
            "gross_eur",
            "has_report",
            "created_at",
            "updated_at",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")
        return queryset.select_related("color", "cut", "treatment").prefetch_related("images")

    def _replace_images(self, stone, images):
        stone.images.all().delete()
        objects = [
            StoneImage(
                stone=stone,
                image_url=image["image_url"],
                display_order=image.get("display_order", index),
            )
            for index, image in enumerate(images)
        ]
        StoneImage.objects.bulk_create(objects)

    def create(self, validated_data):
        images = validated_data.pop("images", None)
        stone = super().create(validated_data)
        if images is not None:
            self._replace_images(stone, images)
        return stone

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
        stone = super().update(instance, validated_data)
        if images is not None:
            self._replace_images(stone, images)
        return stone


REPORT_ADMIN_ONLY_FIELDS = ("note", "owner_telephone", "currency", "price")

REPORT_GEMOLOGICAL_FIELDS = (
    "shape_cutting_style",
    "measurements",
    "carat_weight",
    "specific_gravity",
    "refractive_index",
    "double_refraction",
    "polariscope",
    "pleochroism",
    "chelsea_color_filter",
    "fluorescence_sw",
    "fluorescence_lw",
    "microscope",
    "treatment",
    "origin",
)


class LinkedStoneSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Stone
        fields = ["id", "name", "weight_carats", "mineral", "country"]


class ReportImageSerializer(serializers.ModelSerializer):
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportImage
        fields = [
            "id",
            "image_url",
            "signed_url",
            "title",
            "caption",
            "is_headline",
            "display_order",
            "created_at",
        ]
        read_only_fields = ["id", "signed_url", "created_at"]
        extra_kwargs = {
            "display_order": {"required": False},
            "is_headline": {"required": False},
        }

    def get_signed_url(self, instance):
        return signed_url(instance.image_url)


class ReportPublicSerializer(serializers.ModelSerializer):
    report_images = ReportImageSerializer(many=True, read_only=True, source="images")
    linked_stone = LinkedStoneSummarySerializer(read_only=True)
    stone_id = serializers.PrimaryKeyRelatedField(read_only=True, source="linked_stone")

    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "stone",
            "stone_id",
            "linked_stone",
            "description",
            "first_name",
            "last_name",
            "owner_email",
            "public",
            "created_at",
            "updated_at",
            "report_images",
            *REPORT_GEMOLOGICAL_FIELDS,
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")
        return queryset.select_related("linked_stone").prefetch_related("images")


class ReportAdminSerializer(serializers.ModelSerializer):
    report_images = ReportImageSerializer(many=True, required=False, source="images")
    linked_stone = LinkedStoneSummarySerializer(read_only=True)
    stone_id = serializers.PrimaryKeyRelatedField(
        queryset=Stone.objects.all(),
        source="linked_stone",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "stone",
            "stone_id",
            "linked_stone",
            "description",
            "note",
            "owner",
            "owner_email",
            "first_name",
            "last_name",
            "owner_telephone",
            "public",
            "currency",
            "price",
            "report_images",
            "created_at",
            "updated_at",
            *REPORT_GEMOLOGICAL_FIELDS,
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")
        return queryset.select_related("linked_stone", "owner").prefetch_related("images")

    def validate_stone_id(self, value):
        if value is None:
            return value
        existing = Report.objects.filter(linked_stone=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("STONE_ALREADY_LINKED")
        return value

    def _replace_images(self, report, images):
        report.images.all().delete()
        objects = [
            ReportImage(
                report=report,
                image_url=image["image_url"],
                title=image.get("title"),
                caption=image.get("caption"),
                is_headline=image.get("is_headline", False),
                display_order=image.get("display_order", index),
            )
            for index, image in enumerate(images)
        ]
        ReportImage.objects.bulk_create(objects)

    def create(self, validated_data):
        images = validated_data.pop("images", None)
        report = super().create(validated_data)
        if images is not None:
            self._replace_images(report, images)
        return report

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
        report = super().update(instance, validated_data)
        if images is not None:
            self._replace_images(report, images)
        return report
