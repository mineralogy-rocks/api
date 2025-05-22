# -*- coding: UTF-8 -*-
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from .models import Chunk
from .models import Queue


class ChunkSerializer(serializers.ModelSerializer):
    is_last = serializers.BooleanField(write_only=True)

    class Meta:
        model = Chunk
        fields = [
            "name",
            "file",
            "version",
            "is_last",
        ]

    def create(self, validated_data):
        parent = validated_data.pop("parent")
        is_last = validated_data.pop("is_last")
        data = {
            "parent": parent,
        }

        if parent.chunks.exists() and parent.status == Queue.STATUS_PARSED:
            data["version"] = parent.chunks.aggregate(max_version=Max("version"))["max_version"] + 1

        chunk = Chunk.objects.create(**validated_data, **data)
        if is_last:
            parent.status = Queue.STATUS_PARSED
            parent.parsed_at = timezone.now()
            parent.save()
        return chunk


class QueueSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)
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
