# -*- coding: UTF-8 -*-
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import authentication
from rest_framework import filters
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .filters import QueueFilter
from .models import Queue
from .serializers import ChunkSerializer
from .serializers import QueueSerializer


class QueueViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "delete"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [
        # permissions.IsAuthenticated,
        # IsOwnerPermission,
    ]
    lookup_field = "uuid"

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    filterset_class = QueueFilter

    def get_serializer_class(self):
        if action in ["add_chunk"]:
            return ChunkSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        super().perform_create(serializer)

    @action(detail=True, methods=["get"])
    def chunks(self, request, uuid=None):
        queue = self.get_object()
        serializer = ChunkSerializer(queue.chunks.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="add-chunk")
    def add_chunk(self, request, uuid=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chunk = serializer.save()
        return Response(ChunkSerializer(chunk).data, status=status.HTTP_201_CREATED)
