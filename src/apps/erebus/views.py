# -*- coding: UTF-8 -*-
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from rest_framework import authentication
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Chunk
from .models import Queue
from .serializers import QueueCreateUpdateSerializer


class QueueViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "delete"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = Queue.objects.all()
    serializer_class = QueueCreateUpdateSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [
        # permissions.IsAuthenticated,
        # IsOwnerPermission,
    ]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        queue = self.get_object()
        file = request.data.get("file")
        if not isinstance(file, SimpleUploadedFile):
            return Response(
                {"file": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunk = Chunk.objects.create(
            queue=queue,
            file=file,
        )

        return Response(
            {
                "id": chunk.id,
                "queue": queue.id,
                "file": chunk.file.url,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        queue = self.get_object()
        chunks = queue.chunks.all()
        if not chunks.exists():
            return Response(
                {"chunks": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for chunk in chunks:
                chunk.file.seek(0)
                queue.file.save(chunk.file.name, chunk.file, save=False)
                chunk.delete()

        return Response(
            {
                "id": queue.id,
                "file": queue.file.url,
            },
            status=status.HTTP_201_CREATED,
        )
