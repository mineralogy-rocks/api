# -*- coding: UTF-8 -*-
from rest_framework import serializers

from .models import Queue


class QueueCreateUpdateSerializer(serializers.ModelSerializer):
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

    # @staticmethod
    # def _get_mime_type(file: UploadedFile) -> str:
    #     import magic
    #
    #     mime = magic.Magic(mime=True)
    #     return mime.from_buffer(file.read(1024))
    #
    # def create(self, validated_data):
    #     file = validated_data.pop("file")
    #
    #     size = file.size
    #     mime_type = (self._get_mime_type(file),)
    #
    #     if size > 1024 * 1024 * 10:
    #         raise serializers.ValidationError("File size exceeds 10MB limit")
    #
    #     file.seek(0, 2)
    #     if file.tell() == 0:
    #         raise serializers.ValidationError("File is empty")
    #
    #     if mime_type not in ALLOWED_MIME_TYPES:
    #         raise serializers.ValidationError("Invalid file type")
    #
    #     queue = Queue.objects.create(file=file, size=size, mime_type=self._get_mime_type(file), **validated_data)
    #     return queue
