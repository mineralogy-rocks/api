# -*- coding: UTF-8 -*-
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_api_key.permissions import HasAPIKey
from rest_framework_simplejwt.authentication import JWTAuthentication

from .filters import PostFilter
from .models import Category
from .models import Post
from .models import Tag
from .serializers import BlogAuthorSerializer
from .serializers import CategoryListSerializer
from .serializers import PostDetailSerializer
from .serializers import PostListSerializer
from .serializers import TagListSerializer


class TagViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    queryset = Tag.objects.all()
    serializer_class = TagListSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]
    renderer_classes = [
        JSONRenderer,
        BrowsableAPIRenderer,
    ]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    filterset_fields = ["name"]
    ordering_fields = ["id", "name"]
    ordering = ["id"]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CategoryViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    queryset = Category.objects.all()
    serializer_class = CategoryListSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]
    renderer_classes = [
        JSONRenderer,
        BrowsableAPIRenderer,
    ]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    filterset_fields = ["name"]
    ordering_fields = ["id", "name"]
    ordering = ["id"]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AuthorViewSet(GenericViewSet, ListModelMixin):
    serializer_class = BlogAuthorSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]
    renderer_classes = [
        JSONRenderer,
        BrowsableAPIRenderer,
    ]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def get_queryset(self):
        return (
            get_user_model()
            .objects.filter(posts__is_published=True)
            .distinct()
            .order_by("first_name", "last_name", "id")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PostViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    queryset = Post.objects.filter(is_published=True)
    serializer_class = PostListSerializer
    permission_classes = [HasAPIKey | IsAuthenticated]
    renderer_classes = [
        JSONRenderer,
        BrowsableAPIRenderer,
    ]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    filterset_class = PostFilter
    ordering_fields = ["id", "name", "description", "content", "views", "likes", "tags", "category", "published_at"]
    ordering = ["-published_at"]

    def get_queryset(self):
        queryset = super().get_queryset()

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=self.request)

        return queryset.prefetch_related("authors").distinct()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return self.serializer_class

    @action(detail=True, methods=["get"], url_path="views")
    def views(self, request, slug=None):
        post = get_object_or_404(Post, slug=slug)
        return Response({"count": post.views})

    @action(detail=True, methods=["get"], url_path="likes")
    def likes(self, request, slug=None):
        post = get_object_or_404(Post, slug=slug)
        return Response({"count": post.likes})

    @action(detail=True, methods=["post"], url_path="increment-views")
    def increment_views(self, request, slug=None):
        post = get_object_or_404(Post, slug=slug)
        post.views += 1
        post.save()
        return Response({"views": post.views})

    @action(detail=True, methods=["post"], url_path="increment-likes")
    def increment_likes(self, request, slug=None):
        post = get_object_or_404(Post, slug=slug)
        post.likes += 1
        post.save()
        return Response({"likes": post.likes})
