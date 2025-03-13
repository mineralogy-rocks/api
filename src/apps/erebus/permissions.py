# -*- coding: UTF-8 -*-
from rest_framework import permissions


class IsOwnerPermission(permissions.BasePermission):
    message = "Only the owner of this object can access it."

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
