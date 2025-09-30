# -*- coding: UTF-8 -*-

from django.db.models import Q
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

from .filters import ChunkFilter
from .filters import PromptFilter
from .filters import QueueFilter
from .mixins import CodeVersionMixin
from .models import Chunk
from .models import Component
from .models import Prompt
from .models import Queue
from .serializers import AIResponseSerializer
from .serializers import BaseChunkSerializer
from .serializers import ChunkIssueSerializer
from .serializers import ChunkSerializer
from .serializers import ComponentSerializer
from .serializers import PromptSerializer
from .serializers import QueueSerializer
from .serializers import QueueToProcessSerializer


class QueueViewSet(CodeVersionMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "delete"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [
        # permissions.IsAuthenticated,
        #
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
        elif self.action in ["add_ai_response"]:
            return AIResponseSerializer
        elif self.action in ["awaiting_processing"]:
            return QueueToProcessSerializer
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

    @action(detail=True, methods=["post"], url_path="add-ai-response")
    def add_ai_response(self, request, uuid=None):
        queue = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ai_response = serializer.save(queue=queue)
        return Response(AIResponseSerializer(ai_response).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="awaiting-processing")
    def awaiting_processing(self, request):
        return super().list(request)


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = Chunk.objects.all()
    permission_classes = [
        # permissions.IsAuthenticated,
    ]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    filterset_class = ChunkFilter

    def get_serializer_class(self):
        if self.action in ["list", "awaiting_processing"]:
            return BaseChunkSerializer
        return ChunkSerializer

    def get_object(self):
        lookup_value = self.kwargs[self.lookup_field]

        try:
            if lookup_value.isdigit():
                return self.get_queryset().get(id=lookup_value)
            else:
                return self.get_queryset().get(hash=lookup_value)
        except Chunk.DoesNotExist:
            return super().get_object()

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related("parent", "code_version")
        return queryset

    @action(detail=False, methods=["get"], url_path="awaiting-processing")
    def awaiting_processing(self, request):
        _queues = Queue.objects.filter(status=Queue.STATUS_PARSED)

        _chunk_ids = []
        for _queue in _queues:
            _latest_version = _queue.chunks.order_by("-version").first()
            if _latest_version:
                _chunk_ids += _queue.chunks.filter(
                    Q(version=_latest_version.version) & (Q(extract_composition=1) | Q(extract_metadata=1))
                ).values_list("id", flat=True)

        queryset = Chunk.objects.filter(id__in=_chunk_ids)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer_class = self.get_serializer_class()
            serializer = serializer_class(page, context={"request": request}, many=True)
            return self.get_paginated_response(serializer.data)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(queryset, context={"request": request}, many=True)
        return Response(serializer.data)


class PromptViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get"]

    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    permission_classes = [
        # permissions.IsAuthenticated,
    ]

    queryset = Prompt.objects.all()
    serializer_class = PromptSerializer

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    filterset_class = PromptFilter

    @action(detail=False, methods=["get"])
    def latest(self, request):
        _prompt = self.filter_queryset(self.get_queryset())
        if _prompt.exists():
            serializer = self.get_serializer(_prompt.latest("created_at"))
            return Response(serializer.data)
        return Response(status=status.HTTP_404_NOT_FOUND)


class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get"]

    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    permission_classes = [
        # permissions.IsAuthenticated,
    ]

    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    pagination_class = None
