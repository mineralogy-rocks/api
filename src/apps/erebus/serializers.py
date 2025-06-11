# -*- coding: UTF-8 -*-
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from .models import Chunk
from .models import ChunkIssue
from .models import CodeVersion
from .models import Queue


class CodeVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeVersion
        fields = [
            "id",
            "name",
        ]

    def to_internal_value(self, data):
        print(data)
        try:
            return self.Meta.model.objects.get(name=data["name"])
        except self.Meta.model.DoesNotExist:
            return self.Meta.model.objects.create(name=data["name"])


class ChunkSerializer(serializers.ModelSerializer):
    is_last = serializers.BooleanField(write_only=True)
    code_version = CodeVersionSerializer()

    class Meta:
        model = Chunk
        fields = [
            "name",
            "file",
            "version",
            "code_version",
            "is_last",
        ]

    def create(self, validated_data):
        parent = validated_data.pop("parent")
        is_last = validated_data.pop("is_last")
        data = {
            "parent": parent,
        }

        if parent.chunks.exists() and parent.status in [Queue.STATUS_PARSING_FAILED]:
            data["version"] = parent.chunks.aggregate(max_version=Max("version"))["max_version"] + 1

        chunk = Chunk.objects.create(**validated_data, **data)
        if is_last:
            parent.status = Queue.STATUS_PARSED
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
