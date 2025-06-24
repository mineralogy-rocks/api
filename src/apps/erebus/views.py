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
from .mixins import CodeVersionMixin
from .models import Chunk
from .models import Queue
from .serializers import ChunkIssueSerializer
from .serializers import ChunkSerializer
from .serializers import QueueSerializer


class QueueViewSet(CodeVersionMixin, viewsets.ModelViewSet):
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

    def get_queryset(self):
        queryset = super().get_queryset()

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=self.request)

        return queryset

    def get_serializer_class(self):
        if self.action in ["add_chunk"]:
            return ChunkSerializer
        elif self.action in ["add_issue"]:
            return ChunkIssueSerializer
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
        queue = self.get_object()
        _data = request.data.copy()
        code_version = self.generate_code_version()
        if code_version:
            _data["code_version"] = code_version.id
        serializer = self.get_serializer(data=_data)
        serializer.is_valid(raise_exception=True)

        chunk = serializer.save(parent=queue)
        return Response(ChunkSerializer(chunk).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path=r"(?P<chunk_id>\d+)")
    def get_chunk(self, request, uuid=None, chunk_id=None):
        queue = self.get_object()
        try:
            chunk = queue.chunks.get(id=chunk_id)
            serializer = ChunkSerializer(chunk)
            return Response(serializer.data)
        except Chunk.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path=r"(?P<chunk_id>\d+)/add-issue")
    def add_issue(self, request, uuid=None, chunk_id=None):
        queue = self.get_object()
        try:
            chunk = queue.chunks.get(id=chunk_id)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            issue = serializer.save(chunk=chunk)
            return Response(ChunkIssueSerializer(issue).data, status=status.HTTP_201_CREATED)
        except Chunk.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
