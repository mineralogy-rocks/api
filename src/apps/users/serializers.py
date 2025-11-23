# -*- coding: UTF-8 -*-
from rest_framework import serializers

from users.models import Space
from users.models import SpaceCollaborator
from users.models import SpaceTag
from users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "date_joined"]
        read_only_fields = ["id", "email", "date_joined"]


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]

    def validate_username(self, value):
        if value and len(value.strip()) == 0:
            raise serializers.ValidationError("Username cannot be empty or whitespace only.")

        if value:
            user = self.instance
            if User.objects.filter(username=value).exclude(pk=user.pk).exists():
                raise serializers.ValidationError("A user with this username already exists.")

        return value


class SpaceTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceTag
        fields = ["id", "name"]
        read_only_fields = ["id"]

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name"]
        read_only_fields = ["id", "email"]


class SpaceCollaboratorSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user",
        write_only=True,
    )
    permission_level_display = serializers.CharField(
        source="get_permission_level_display",
        read_only=True,
    )

    class Meta:
        model = SpaceCollaborator
        fields = [
            "id",
            "user",
            "user_id",
            "permission_level",
            "permission_level_display",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("user")


class SpaceSerializer(serializers.ModelSerializer):
    owner = UserBasicSerializer(read_only=True)
    collaborators = SpaceCollaboratorSerializer(many=True, read_only=True)
    tags = SpaceTagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=SpaceTag.objects.all(),
        many=True,
        source="tags",
        write_only=True,
        required=False,
    )
    access_display = serializers.CharField(source="get_access_display", read_only=True)

    class Meta:
        model = Space
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "access",
            "access_display",
            "tags",
            "tag_ids",
            "collaborators",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("owner").prefetch_related(
            "tags",
            "collaborators__user",
        )

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class SpaceCreateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=SpaceTag.objects.all(),
        many=True,
        source="tags",
        required=False,
    )

    class Meta:
        model = Space
        fields = ["name", "description", "access", "tag_ids"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class SpaceUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=SpaceTag.objects.all(),
        many=True,
        source="tags",
        required=False,
    )

    class Meta:
        model = Space
        fields = ["name", "description", "access", "tag_ids"]
