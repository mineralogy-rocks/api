# -*- coding: UTF-8 -*-
from django.utils import timezone
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
        required=False,
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
            "is_pending",
            "is_accepted",
            "is_revoked",
            "invited_email",
            "invitation_sent_at",
            "invitation_expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_pending",
            "is_accepted",
            "is_revoked",
            "invited_email",
            "invitation_sent_at",
            "invitation_expires_at",
            "created_at",
        ]

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
        fields = ["id", "name", "description", "access", "tag_ids"]

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
        fields = ["id", "name", "description", "access", "tag_ids"]


class SpaceInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    permission_level = serializers.IntegerField(required=True)

    def validate_permission_level(self, value):
        from users.models import SpaceCollaborator

        valid_levels = [
            SpaceCollaborator.PERMISSION_VIEWER,
            SpaceCollaborator.PERMISSION_ADMIN,
            SpaceCollaborator.PERMISSION_SUPERADMIN,
        ]
        if value not in valid_levels:
            raise serializers.ValidationError("Invalid permission level")
        return value


class PendingInvitationSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source="space.name", read_only=True)
    space_id = serializers.IntegerField(source="space.id", read_only=True)
    space_description = serializers.CharField(source="space.description", read_only=True)
    inviter_name = serializers.SerializerMethodField()
    permission_level_display = serializers.CharField(
        source="get_permission_level_display",
        read_only=True,
    )

    class Meta:
        model = SpaceCollaborator
        fields = [
            "id",
            "space_id",
            "space_name",
            "space_description",
            "inviter_name",
            "permission_level",
            "permission_level_display",
            "invitation_sent_at",
            "invitation_expires_at",
        ]

    def get_inviter_name(self, obj):
        inviter = obj.space.owner
        return inviter.get_full_name() or inviter.username or inviter.email


class InvitationResponseSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)


class SentInvitationSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source="space.name", read_only=True)
    space_id = serializers.IntegerField(source="space.id", read_only=True)
    invitee_email = serializers.SerializerMethodField()
    invitee_name = serializers.SerializerMethodField()
    permission_level_display = serializers.CharField(
        source="get_permission_level_display",
        read_only=True,
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = SpaceCollaborator
        fields = [
            "id",
            "space_id",
            "space_name",
            "invitee_email",
            "invitee_name",
            "permission_level",
            "permission_level_display",
            "is_pending",
            "is_accepted",
            "is_revoked",
            "status",
            "invitation_sent_at",
            "invitation_expires_at",
            "created_at",
        ]

    def get_invitee_email(self, obj):
        return obj.invited_email or (obj.user.email if obj.user else None)

    def get_invitee_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username or obj.user.email
        return obj.invited_email

    def get_status(self, obj):
        if obj.is_revoked:
            return "Revoked"
        elif obj.is_accepted:
            return "Accepted"
        elif obj.is_accepted is False:
            return "Declined"
        elif obj.is_pending:
            if obj.invitation_expires_at and obj.invitation_expires_at < timezone.now():
                return "Expired"
            return "Pending"
        return "Unknown"
