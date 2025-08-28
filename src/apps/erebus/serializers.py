# -*- coding: UTF-8 -*-
from django.utils import timezone
from rest_framework import serializers

from .models import Chunk
from .models import ChunkIssue
from .models import ChunkResponse
from .models import CodeVersion
from .models import Prompt
from .models import Queue


class ChunkSerializer(serializers.ModelSerializer):
    code_version = serializers.PrimaryKeyRelatedField(
        queryset=CodeVersion.objects.all(), required=False, allow_null=True
    )
    status = serializers.ChoiceField(choices=Queue.STATUS_CHOICES, write_only=True, required=False)

    class Meta:
        model = Chunk
        fields = [
            "name",
            "file",
            "version",
            "code_version",
            "status",
            "head",
            "extract_composition",
            "extract_metadata",
        ]

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

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = [
            "chunks__code_version",
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


class ChunkResponseSerializer(serializers.ModelSerializer):
    prompt = serializers.PrimaryKeyRelatedField(queryset=Prompt.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ChunkResponse
        fields = [
            "id",
            "response",
            "clean_response",
            "prompt",
            "is_extracted",
            "is_error",
            "exception",
        ]

    def create(self, validated_data):
        chunk = validated_data.pop("chunk")

        return ChunkResponse.objects.create(chunk=chunk, **validated_data)


class PromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prompt
        fields = [
            "id",
            "text",
            "type",
            "created_at",
        ]
