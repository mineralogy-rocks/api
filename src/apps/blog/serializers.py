# -*- coding: UTF-8 -*-
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category
from .models import Channel
from .models import Post
from .models import Tag
from .storage import public_url


class TagListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
        ]


class CategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
        ]


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
        ]


class PostAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "first_name",
            "last_name",
            "linkedin_url",
        ]


class BlogAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "first_name",
            "last_name",
        ]


class PostListSerializer(serializers.ModelSerializer):
    tags = TagListSerializer(many=True)
    category = CategoryListSerializer()
    authors = PostAuthorSerializer(many=True, read_only=True)
    channels = ChannelSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()
    url = serializers.HyperlinkedIdentityField(view_name="blog:post-detail", lookup_field="slug")

    class Meta:
        model = Post
        fields = [
            "id",
            "name",
            "slug",
            "url",
            "description",
            "cover_image",
            "views",
            "likes",
            "tags",
            "category",
            "authors",
            "channels",
            "published_at",
        ]

    def get_cover_image(self, instance):
        return public_url(instance.cover_image)

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = [
            "category",
        ]
        prefetch_related = [
            "tags",
            "authors",
            "channels",
        ]

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset


class PostDetailSerializer(serializers.ModelSerializer):
    tags = TagListSerializer(many=True)
    category = CategoryListSerializer()
    authors = PostAuthorSerializer(many=True, read_only=True)
    channels = ChannelSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "content",
            "content_json",
            "stone",
            "cover_image",
            "views",
            "likes",
            "tags",
            "category",
            "authors",
            "channels",
            "created_at",
            "updated_at",
            "is_published",
            "published_at",
        ]

    def get_cover_image(self, instance):
        return public_url(instance.cover_image)


class PostAdminSerializer(serializers.ModelSerializer):
    tags = TagListSerializer(many=True, read_only=True)
    tag_names = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    channels = ChannelSerializer(many=True, read_only=True)
    channel_slugs = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=get_user_model().objects.all(),
        required=False,
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "content",
            "content_json",
            "stone",
            "cover_image",
            "category",
            "is_published",
            "published_at",
            "tags",
            "tag_names",
            "channels",
            "channel_slugs",
            "authors",
            "views",
            "likes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "views",
            "likes",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"content": {"required": False, "allow_blank": True}}

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")
        return queryset.select_related("category").prefetch_related("tags", "authors", "channels")

    def validate_channel_slugs(self, value):
        channels = list(Channel.objects.filter(slug__in=value))
        found = {channel.slug for channel in channels}
        missing = [slug for slug in value if slug not in found]
        if missing:
            raise serializers.ValidationError(f"Unknown channel(s): {', '.join(missing)}")
        return channels

    def _apply_tags(self, post, tag_names):
        if tag_names is None:
            return
        tags = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
        post.tags.set(tags)

    def create(self, validated_data):
        tag_names = validated_data.pop("tag_names", None)
        channels = validated_data.pop("channel_slugs", None)
        post = super().create(validated_data)
        self._apply_tags(post, tag_names)
        if channels is not None:
            post.channels.set(channels)
        return post

    def update(self, instance, validated_data):
        tag_names = validated_data.pop("tag_names", None)
        channels = validated_data.pop("channel_slugs", None)
        post = super().update(instance, validated_data)
        self._apply_tags(post, tag_names)
        if channels is not None:
            post.channels.set(channels)
        return post
