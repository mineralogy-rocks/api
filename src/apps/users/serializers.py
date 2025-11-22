# -*- coding: UTF-8 -*-
from rest_framework import serializers

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
