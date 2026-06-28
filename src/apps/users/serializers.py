# -*- coding: UTF-8 -*-
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import serializers
from users.encryption import decrypt_value
from users.encryption import encrypt_value
from users.models import Space
from users.models import SpaceCollaborator
from users.models import User
from users.models import UserTag


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "is_staff", "date_joined"]
        read_only_fields = ["id", "email", "is_staff", "date_joined"]


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


class UserTagSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = UserTag
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_name(self, obj):
        return decrypt_value(obj.name_encrypted)

    def validate(self, attrs):
        name = self.initial_data.get("name", "").strip()

        if not name:
            raise serializers.ValidationError({"name": "Tag name cannot be empty."})

        user = self.context["request"].user

        queryset = self.Meta.model.objects.filter(user=user)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        for tag in queryset:
            existing_name = decrypt_value(tag.name_encrypted)
            if existing_name.lower() == name.lower():
                raise serializers.ValidationError({"name": "You already have a tag with this name."})

        attrs["name_encrypted"] = encrypt_value(name)
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class UserTagReadSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = UserTag
        fields = ["id", "name"]

    def get_name(self, obj):
        return decrypt_value(obj.name_encrypted)


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


class CollaboratorListSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    permission_level_display = serializers.CharField(
        source="get_permission_level_display",
        read_only=True,
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = SpaceCollaborator
        fields = [
            "id",
            "user",
            "permission_level",
            "permission_level_display",
            "is_pending",
            "is_accepted",
            "is_revoked",
            "invited_email",
            "invited_by",
            "invitation_sent_at",
            "invitation_expires_at",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "permission_level",
            "permission_level_display",
            "is_pending",
            "is_accepted",
            "is_revoked",
            "invited_email",
            "invited_by",
            "invitation_sent_at",
            "invitation_expires_at",
            "status",
            "created_at",
        ]

    def get_status(self, obj):
        if obj.is_revoked:
            return "Revoked"
        elif obj.is_accepted:
            return "Active"
        elif obj.is_pending:
            if obj.invitation_expires_at and obj.invitation_expires_at < timezone.now():
                return "Expired"
            return "Pending"
        return "Unknown"

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("user", "invited_by")


class SpaceSerializer(serializers.ModelSerializer):
    owner = UserBasicSerializer(read_only=True)
    collaborators = SpaceCollaboratorSerializer(many=True, read_only=True)
    tags = UserTagReadSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=UserTag.objects.none(),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            self.fields["tag_ids"].queryset = UserTag.objects.filter(user=request.user)

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset, request = kwargs.get("queryset"), kwargs.get("request")
        _select_related = ["owner"]
        _prefetch_related = ["tags", "collaborators__user"]
        return queryset.select_related(*_select_related).prefetch_related(
            "collaborators__user", Prefetch("tags", queryset=UserTag.objects.filter(user=request.user))
        )

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class SpaceCreateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=UserTag.objects.none(),
        many=True,
        source="tags",
        required=False,
    )

    class Meta:
        model = Space
        fields = ["id", "name", "description", "access", "tag_ids"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            self.fields["tag_ids"].child_relation.queryset = UserTag.objects.filter(user=request.user)

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class SpaceUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=UserTag.objects.none(),
        many=True,
        source="tags",
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Space
        fields = ["id", "name", "description", "access", "tag_ids"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            self.fields["tag_ids"].child_relation.queryset = UserTag.objects.filter(user=request.user)


class SpaceInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    permission_level = serializers.IntegerField(required=True)

    def validate_permission_level(self, value):
        valid_levels = [
            SpaceCollaborator.PERMISSION_VIEWER,
            SpaceCollaborator.PERMISSION_ADMIN,
            SpaceCollaborator.PERMISSION_SUPERADMIN,
        ]
        if value not in valid_levels:
            raise serializers.ValidationError("Invalid permission level")
        return value


class InvitationResponseSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)


class AcceptInvitationWithPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, min_length=8)
    password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match"})
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, min_length=8)
