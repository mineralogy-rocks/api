# -*- coding: UTF-8 -*-
from rest_framework import permissions

from users.models import SpaceCollaborator


class IsSpaceOwnerOrCollaborator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user.is_authenticated:
            return False

        if obj.owner == user:
            return True

        try:
            collaborator = SpaceCollaborator.objects.get(
                space=obj,
                user=user,
                is_pending=False,
                is_accepted=True,
                is_revoked=False,
            )
        except SpaceCollaborator.DoesNotExist:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if view.action == "transfer_ownership":
            return False

        if collaborator.permission_level == SpaceCollaborator.PERMISSION_SUPERADMIN:
            return True

        if collaborator.permission_level == SpaceCollaborator.PERMISSION_ADMIN:
            if view.action in [
                "update",
                "partial_update",
                "invite_collaborator",
                "remove_collaborator",
            ]:
                return True

        return False
