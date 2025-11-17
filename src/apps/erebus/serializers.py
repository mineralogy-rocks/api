# -*- coding: UTF-8 -*-
from django.utils import timezone
from rest_framework import serializers

from .models import AIResponse
from .models import Component
from .models import Prompt
from .models import PromptTag
from .models import PromptType
from .models import Queue
from .models import Unit
from .services import FileConversionService
from .services import TextCleaningService


class QueueSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)

    class Meta:
        model = Queue
        fields = [
            "uuid",
            "hash",
            "name",
            "description",
            "status",
            "file",
            "markdown",
            "size",
            "mime_type",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_conversion_service = FileConversionService()
        self.text_cleaning_service = TextCleaningService()

    def validate_file(self, file):
        import os

        if file.size > Queue.MAX_SIZE_ALLOWED:
            raise serializers.ValidationError("File size exceeds 10MB limit")

        ext = os.path.splitext(file.name)[1][1:].lower()
        if ext not in Queue.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file format. Allowed formats: {', '.join(Queue.ALLOWED_EXTENSIONS)}"
            )
        return file

    def create(self, validated_data):
        file_obj = validated_data.get("file")

        if file_obj:
            markdown_content = self.file_conversion_service.convert_to_markdown(file_obj)
            markdown_content = self.text_cleaning_service.clean_markdown(markdown_content)
            validated_data["markdown"] = markdown_content.strip()

        return super().create(validated_data)

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = []

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset

    def update(self, instance, validated_data):
        _status = validated_data.get("status", None)
        if _status and _status in [Queue.STATUS_AI_GENERATED]:
            instance.ai_generated_at = timezone.now()
        return super().update(instance, validated_data)


class QueueToProcessSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)

    class Meta:
        model = Queue
        fields = [
            "uuid",
            "hash",
            "name",
            "description",
            "status",
            "file",
            "size",
            "mime_type",
            "markdown",
            "extract_composition",
            "extract_metadata",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = []

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset


class AIResponseSerializer(serializers.ModelSerializer):
    queue = serializers.SlugRelatedField(slug_field="uuid", queryset=Queue.objects.all(), required=True)
    prompt = serializers.PrimaryKeyRelatedField(queryset=Prompt.objects.all(), required=False)

    class Meta:
        model = AIResponse
        fields = [
            "id",
            "hash",
            "batch",
            "queue",
            "prompt",
            "model",
            "request_raw",
            "response_raw",
            "response_parsed",
            "is_error",
            "exception",
            "scheduled_at",
            "processed_at",
            "answered_at",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ]

    def create(self, validated_data):
        _exception = validated_data.get("exception", None)
        if _exception:
            validated_data["is_error"] = True
        return super().create(validated_data)


class PromptTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptTag
        fields = [
            "key",
            "value",
        ]


class PromptTypeSerializer(serializers.ModelSerializer):
    tags = PromptTagSerializer(many=True)

    class Meta:
        model = PromptType
        fields = [
            "id",
            "name",
            "tags",
        ]


class PromptSerializer(serializers.ModelSerializer):
    type = PromptTypeSerializer()

    class Meta:
        model = Prompt
        fields = [
            "id",
            "openai_id",
            "text",
            "type",
            "created_at",
        ]


class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = [
            "id",
            "name",
            "is_major",
        ]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            "id",
            "name",
        ]
