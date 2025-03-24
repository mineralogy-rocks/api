# -*- coding: UTF-8 -*-
from django.utils import timezone
from rest_framework import serializers

from .models import Chunk
from .models import Queue


class QueueSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)

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


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = [
            "name",
            "file",
            "is_processed",
            "is_error",
        ]

    def create(self, validated_data):
        queue = validated_data.get("queue")
        queue.parsed_at = timezone.now()
        return Chunk.objects.create(**validated_data)
