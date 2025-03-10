# -*- coding: UTF-8 -*-
from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

from .constants import ALLOWED_MIME_TYPES
from .models import Queue


class QueueCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Queue
        fields = [
            "name",
            "description",
            "status",
            "file",
            "size",
            "mime_type",
        ]

    @staticmethod
    def _get_mime_type(file: UploadedFile) -> str:
        import magic

        mime = magic.Magic(mime=True)
        return mime.from_buffer(file.read(1024))

    def create(self, validated_data):
        file = validated_data.pop("file")

        size = file.size
        mime_type = (self._get_mime_type(file),)

        if size > 1024 * 1024 * 10:
            raise serializers.ValidationError("File size exceeds 10MB limit")

        file.seek(0, 2)
        if file.tell() == 0:
            raise serializers.ValidationError("File is empty")

        if mime_type not in ALLOWED_MIME_TYPES:
            raise serializers.ValidationError("Invalid file type")

        queue = Queue.objects.create(file=file, size=size, mime_type=self._get_mime_type(file), **validated_data)
        return queue
