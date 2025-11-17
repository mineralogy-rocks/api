# -*- coding: UTF-8 -*-
import os
import re
import tempfile

import pandas as pd
from django.db import models
from django.utils import timezone
from markitdown import MarkItDown
from rest_framework import serializers

from .models import AIResponse
from .models import Chunk
from .models import ChunkIssue
from .models import CodeVersion
from .models import Component
from .models import Prompt
from .models import PromptTag
from .models import PromptType
from .models import Queue
from .models import Unit


class BaseChunkSerializer(serializers.ModelSerializer):
    code_version = serializers.PrimaryKeyRelatedField(
        queryset=CodeVersion.objects.all(), required=False, allow_null=True
    )
    status = serializers.ChoiceField(choices=Queue.STATUS_CHOICES, write_only=True, required=False)
    url = serializers.HyperlinkedIdentityField(
        view_name="erebus:chunk-detail", read_only=True, lookup_url_kwarg="pk", lookup_field="hash"
    )

    class Meta:
        model = Chunk
        fields = [
            "hash",
            "version",
            "code_version",
            "status",
            "extract_composition",
            "extract_metadata",
            "url",
        ]


class ChunkSerializer(BaseChunkSerializer):
    class Meta:
        model = Chunk
        fields = BaseChunkSerializer.Meta.fields + ["data"]

    def create(self, validated_data):
        parent = validated_data.pop("parent")
        status = validated_data.pop("status", None)
        data = {
            "parent": parent,
        }

        chunk = Chunk.objects.create(**validated_data, **data)

        if status:
            parent.status = status

            if status in [Queue.STATUS_PARSED]:
                parent.parsed_at = timezone.now()

            parent.save()

        return chunk


class QueueSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)
    parsing_version = serializers.IntegerField(read_only=True, default=0)
    chunks = BaseChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Queue
        fields = [
            "uuid",
            "name",
            "description",
            "status",
            "file",
            "markdown",
            "size",
            "mime_type",
            "parsing_version",
            "chunks",
        ]

    def validate_file(self, file):
        if file.size > Queue.MAX_SIZE_ALLOWED:
            raise serializers.ValidationError("File size exceeds 10MB limit")

        import os

        ext = os.path.splitext(file.name)[1][1:].lower()
        if ext not in Queue.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file format. Allowed formats: {', '.join(Queue.ALLOWED_EXTENSIONS)}"
            )
        return file

    def create(self, validated_data):
        file_obj = validated_data.get("file")

        if file_obj:
            file_extension = os.path.splitext(file_obj.name)[1].lower()

            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension, mode="wb") as tmp_file:
                file_obj.seek(0)
                file_content = file_obj.read()
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            file_obj.seek(0)

            markdown_content = ""

            if file_extension in [".xls", ".xlsx", ".csv"]:
                if file_extension == ".csv":
                    df = pd.read_csv(tmp_file_path, on_bad_lines="skip")
                else:
                    df = pd.read_excel(tmp_file_path)

                df = df.fillna("")
                markdown_content = df.to_markdown(index=False)
            else:
                md = MarkItDown()
                result = md.convert(tmp_file_path)
                markdown_content = result.text_content

                markdown_content = re.sub(r"\bnan\b", "", markdown_content, flags=re.IGNORECASE)
                markdown_content = re.sub(r"\b-?inf\b", "", markdown_content, flags=re.IGNORECASE)

            markdown_content = re.sub(r" +", " ", markdown_content)
            markdown_content = re.sub(r"\n\n+", "\n\n", markdown_content)

            validated_data["markdown"] = markdown_content.strip()

            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        return super().create(validated_data)

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = [
            "chunks__code_version",
        ]

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset

    def update(self, instance, validated_data):
        _status = validated_data.get("status", None)
        if _status and _status in [Queue.STATUS_AI_GENERATED]:
            instance.ai_generated_at = timezone.now()
        return super().update(instance, validated_data)


class QueueToProcessSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)
    parsing_version = serializers.IntegerField(read_only=True, default=0)
    chunks = ChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Queue
        fields = [
            "uuid",
            "name",
            "description",
            "status",
            "file",
            "size",
            "mime_type",
            "markdown",
            "parsing_version",
            "chunks",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        _max_version = (
            Chunk.objects.filter(parent=models.OuterRef("parent"))
            .values("parent")
            .annotate(max_version=models.Max("version"))
            .values("max_version")
        )

        select_related = []
        prefetch_related = [
            models.Prefetch(
                "chunks",
                queryset=Chunk.objects.filter(models.Q(extract_composition=True) | models.Q(extract_metadata=True))
                .filter(version=models.Subquery(_max_version))
                .select_related("code_version"),
            )
        ]

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset


class ChunkIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChunkIssue
        fields = [
            "id",
            "name",
            "comment",
        ]

    def create(self, validated_data):
        chunk = validated_data.pop("chunk")
        user = validated_data.pop("user", None)

        data = {
            "chunk": chunk,
            "email": user.email if user else None,
        }

        return ChunkIssue.objects.create(**validated_data, **data)


class AIResponseSerializer(serializers.ModelSerializer):
    queue = serializers.SlugRelatedField(slug_field="uuid", queryset=Queue.objects.all(), required=True)
    prompt = serializers.PrimaryKeyRelatedField(queryset=Prompt.objects.all(), required=False)
    chunks = serializers.SlugRelatedField(slug_field="hash", many=True, queryset=Chunk.objects.all())

    class Meta:
        model = AIResponse
        fields = [
            "id",
            "hash",
            "batch",
            "chunks",
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
