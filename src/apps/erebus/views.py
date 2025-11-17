# -*- coding: UTF-8 -*-

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import authentication
from rest_framework import filters
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser
from rest_framework.parsers import JSONParser
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .filters import PromptFilter
from .filters import QueueFilter
from .mixins import CodeVersionMixin
from .models import AIResponse
from .models import Component
from .models import Prompt
from .models import Queue
from .models import Unit
from .serializers import AIResponseSerializer
from .serializers import ComponentSerializer
from .serializers import PromptSerializer
from .serializers import QueueSerializer
from .serializers import QueueToProcessSerializer
from .serializers import UnitSerializer


class QueueViewSet(CodeVersionMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "delete"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
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
        if self.action in ["awaiting_processing"]:
            return QueueToProcessSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        super().perform_create(serializer)

    @action(detail=False, methods=["get"], url_path="awaiting-processing")
    def awaiting_processing(self, request):
        return super().list(request)


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


class AIResponseViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch"]
    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    queryset = AIResponse.objects.all()
    serializer_class = AIResponseSerializer
    permission_classes = [
        # permissions.IsAuthenticated,
    ]
    lookup_field = "hash"

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related("queue", "prompt").prefetch_related("chunks")
        return queryset


class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get"]

    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    permission_classes = [
        # permissions.IsAuthenticated,
    ]

    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    pagination_class = None


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get"]

    authentication_classes = [authentication.SessionAuthentication, JWTAuthentication]
    permission_classes = [
        # permissions.IsAuthenticated,
    ]

    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    pagination_class = None
