# -*- coding: UTF-8 -*-
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes
from rest_framework.decorators import permission_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from users.authentication import CsrfExemptSessionAuthentication
from users.models import Space
from users.models import SpaceCollaborator
from users.models import User
from users.models import UserTag
from users.permissions import IsSpaceOwnerOrCollaborator
from users.serializers import AcceptInvitationWithPasswordSerializer
from users.serializers import CollaboratorListSerializer
from users.serializers import ForgotPasswordSerializer
from users.serializers import InvitationResponseSerializer
from users.serializers import ResetPasswordSerializer
from users.serializers import SpaceCollaboratorSerializer
from users.serializers import SpaceCreateSerializer
from users.serializers import SpaceInvitationSerializer
from users.serializers import SpaceSerializer
from users.serializers import SpaceUpdateSerializer
from users.serializers import UserSerializer
from users.serializers import UserTagSerializer
from users.serializers import UserUpdateSerializer
from users.services import calculate_expiration_date
from users.services import generate_invitation_token
from users.services import generate_password_reset_token
from users.services import send_invitation_email
from users.services import send_password_reset_email
from users.services import validate_invitation_token
from users.services import validate_password_reset_token
from users.tokens import OneTimeToken


class SpacePagination(LimitOffsetPagination):
    default_limit = 6
    max_limit = 100


class CurrentUserView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            user_serializer = UserSerializer(request.user)
            return Response(user_serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    remember_me = request.data.get("remember_me", False)

    if not username or not password:
        return Response(
            {"detail": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)

        if remember_me:
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)

        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)


class SpaceViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsSpaceOwnerOrCollaborator]
    pagination_class = SpacePagination

    REQUIRES_ADMIN = SpaceCollaborator.PERMISSION_ADMIN
    REQUIRES_ANY_COLLABORATOR = SpaceCollaborator.PERMISSION_VIEWER

    def get_queryset(self):
        user = self.request.user
        queryset = Space.objects.filter(
            Q(owner=user)
            | Q(
                collaborators__user=user,
                collaborators__is_accepted=True,
                collaborators__is_revoked=False,
            )
        ).distinct()

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=self.request)

        return queryset

    @action(detail=False, methods=["get"], url_path="my-spaces")
    def my_spaces(self, request):
        queryset = Space.objects.filter(owner=request.user)

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=request)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SpaceSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = SpaceSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="shared-spaces")
    def shared_spaces(self, request):
        user = request.user
        queryset = Space.objects.filter(
            collaborators__user=user,
            collaborators__is_accepted=True,
            collaborators__is_revoked=False,
        )

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=request)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SpaceSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = SpaceSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action == "create":
            return SpaceCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return SpaceUpdateSerializer
        return SpaceSerializer

    def _check_space_permission(self, space, user, min_permission_level):
        """
        Check if user has sufficient permission level for a space.

        Args:
            space: Space instance to check permissions for
            user: User instance to check
            min_permission_level: Minimum required permission level (use class constants)

        Returns:
            tuple: (has_permission: bool, user_permission_level: int|None)
                - has_permission: True if user is owner or has sufficient permission
                - user_permission_level: The user's actual permission level, or None if owner

        Usage:
            Use this helper for additional permission checks beyond standard CRUD operations.
            For standard CRUD, rely on IsSpaceOwnerOrCollaborator permission class.

        Example:
            has_permission, _ = self._check_space_permission(space, user, self.REQUIRES_ADMIN)
            if not has_permission:
                return Response({"detail": "..."}, status=status.HTTP_403_FORBIDDEN)
        """
        if space.owner == user:
            return (True, None)

        try:
            user_collaboration = SpaceCollaborator.objects.get(
                space=space,
                user=user,
                is_pending=False,
                is_accepted=True,
                is_revoked=False,
            )
            if user_collaboration.permission_level >= min_permission_level:
                return (True, user_collaboration.permission_level)
        except SpaceCollaborator.DoesNotExist:
            pass

        return (False, None)

    @action(detail=True, methods=["get"], url_path="collaborators")
    def collaborators(self, request, pk=None):
        space = self.get_object()
        user = request.user

        has_permission, _ = self._check_space_permission(space, user, self.REQUIRES_ADMIN)
        if not has_permission:
            return Response(
                {"detail": "You do not have permission to view collaborators"},
                status=status.HTTP_403_FORBIDDEN,
            )

        collaborators = SpaceCollaborator.objects.filter(space=space)
        collaborators = CollaboratorListSerializer.setup_eager_loading(collaborators)

        serializer = CollaboratorListSerializer(collaborators, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="invite-collaborator")
    def invite_collaborator(self, request, pk=None):
        space = self.get_object()
        serializer = SpaceInvitationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        permission_level = serializer.validated_data["permission_level"]

        if space.owner.email == email:
            return Response(
                {"detail": "Owner cannot be invited as collaborator"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
            is_new_user = False
        except User.DoesNotExist:
            user = User.objects.create_user(
                email=email,
                password=None,
                is_active=False,
            )
            is_new_user = True

        existing_invitation = SpaceCollaborator.objects.filter(
            space=space,
            user=user,
        ).first()

        if existing_invitation and existing_invitation.is_accepted:
            return Response(
                {"detail": "User is already a collaborator"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = generate_invitation_token()
        invitation_sent_at = timezone.now()
        invitation_expires_at = calculate_expiration_date(days=7)

        permission_display = dict(SpaceCollaborator.PERMISSION_CHOICES).get(permission_level)

        if existing_invitation and existing_invitation.is_pending:
            existing_invitation.invitation_token = token
            existing_invitation.invitation_sent_at = invitation_sent_at
            existing_invitation.invitation_expires_at = invitation_expires_at
            existing_invitation.permission_level = permission_level
            existing_invitation.invited_by = request.user
            existing_invitation.save()
            collaboration = existing_invitation
        else:
            collaboration = SpaceCollaborator.objects.create(
                space=space,
                user=user,
                permission_level=permission_level,
                is_pending=True,
                is_accepted=None,
                invitation_token=token,
                invitation_sent_at=invitation_sent_at,
                invitation_expires_at=invitation_expires_at,
                invited_email=email,
                invited_by=request.user,
            )

        send_invitation_email(
            email=email,
            space=space,
            inviter=request.user,
            token=token,
            permission_level_display=permission_display,
            is_new_user=is_new_user,
        )

        serializer = SpaceCollaboratorSerializer(collaboration)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="remove-collaborator")
    def remove_collaborator(self, request, pk=None):
        space = self.get_object()
        collaborator_id = request.data.get("collaborator_id")

        if not collaborator_id:
            return Response(
                {"detail": "collaborator_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            collaborator = SpaceCollaborator.objects.get(
                id=collaborator_id,
                space=space,
            )
            collaborator.delete()
            return Response(
                {"detail": "Collaborator removed successfully"},
                status=status.HTTP_200_OK,
            )
        except SpaceCollaborator.DoesNotExist:
            return Response(
                {"detail": "Collaborator not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="update-collaborator-permission")
    def update_collaborator_permission(self, request, pk=None):
        space = self.get_object()
        collaborator_id = request.data.get("collaborator_id")
        permission_level = request.data.get("permission_level")

        if not collaborator_id or permission_level is None:
            return Response(
                {"detail": "collaborator_id and permission_level are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            collaborator = SpaceCollaborator.objects.get(
                id=collaborator_id,
                space=space,
            )
            collaborator.permission_level = permission_level
            collaborator.save()

            serializer = SpaceCollaboratorSerializer(collaborator)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SpaceCollaborator.DoesNotExist:
            return Response(
                {"detail": "Collaborator not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    def transfer_ownership(self, request, pk=None):
        space = self.get_object()
        new_owner_id = request.data.get("new_owner_id")

        if request.user != space.owner:
            return Response(
                {"detail": "Only the owner can transfer ownership"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not new_owner_id:
            return Response(
                {"detail": "new_owner_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        SpaceCollaborator.objects.filter(space=space, user=new_owner).delete()

        space.owner = new_owner
        space.save()

        serializer = SpaceSerializer(space, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvitationViewSet(viewsets.GenericViewSet):
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="validate",
    )
    def validate_token(self, request):
        """
        GET /user/invitations/validate/?token=...
        Validates token and returns user state for frontend.
        """
        token = request.query_params.get("token")

        if not token:
            return Response(
                {"is_valid": False, "error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation, error = validate_invitation_token(token)

        if error:
            return Response(
                {"is_valid": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requires_password = not invitation.user.has_usable_password()

        inviter_name = (
            (invitation.invited_by.get_full_name() or invitation.invited_by.username or invitation.invited_by.email)
            if invitation.invited_by
            else "Unknown"
        )

        return Response(
            {
                "is_valid": True,
                "requires_password": requires_password,
                "email": invitation.user.email,
                "space_name": invitation.space.name,
                "space_id": str(invitation.space.id),
                "inviter_name": inviter_name,
                "permission_level": invitation.get_permission_level_display(),
            }
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="accept",
    )
    def accept_invitation(self, request):
        serializer = InvitationResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        invitation, error = validate_invitation_token(token)

        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        user = invitation.user

        if not user.has_usable_password():
            return Response(
                {
                    "detail": "New user must set password",
                    "requires_password": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            user.is_active = True
            user.save()

        invitation.is_pending = False
        invitation.is_accepted = True
        invitation.save()

        return Response(
            {
                "detail": "Invitation accepted successfully",
                "space_id": str(invitation.space.id),
                "space_name": invitation.space.name,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="accept-with-password",
    )
    def accept_with_password(self, request):
        """
        POST /user/invitations/accept-with-password/
        Accept invitation and set password for new users.
        """
        serializer = AcceptInvitationWithPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        invitation, error = validate_invitation_token(token)

        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        user = invitation.user

        if user.has_usable_password():
            return Response(
                {"detail": "User already has a password. Use standard accept endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password, user)
        except DjangoValidationError as e:
            return Response(
                {"password": list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.is_active = True
        user.save()

        invitation.is_pending = False
        invitation.is_accepted = True
        invitation.save()

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        return Response(
            {
                "detail": "Invitation accepted and password set successfully",
                "space_id": str(invitation.space.id),
                "space_name": invitation.space.name,
            },
            status=status.HTTP_200_OK,
        )


class UserTagViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserTagSerializer

    def get_queryset(self):
        return UserTag.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PasswordResetViewSet(viewsets.GenericViewSet):
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="forgot",
    )
    def forgot_password(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
            token_obj = generate_password_reset_token(user)
            send_password_reset_email(user, token_obj.token)
        except User.DoesNotExist:
            pass

        return Response(
            {"detail": "If an account with this email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="validate",
    )
    def validate_token(self, request):
        token = request.query_params.get("token")

        if not token:
            return Response({"is_valid": False, "error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        _token, _error = validate_password_reset_token(token)

        if _error:
            return Response(
                {"is_valid": False, "error": _error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"is_valid": True, "email": _token.user.email}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="reset",
    )
    def reset_password(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        _token, _error = validate_password_reset_token(token)

        if _error:
            return Response({"detail": _error}, status=status.HTTP_400_BAD_REQUEST)

        user = _token.user

        try:
            validate_password(password, user)
        except DjangoValidationError as e:
            return Response({"password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()

        _token.is_used = True
        _token.save()

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        return Response({"detail": "Password has been reset successfully"}, status=status.HTTP_200_OK)


class SessionExchangeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.data.get("token")
        if not raw:
            return Response({"detail": "token is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ott = OneTimeToken(raw)
        except TokenError:
            return Response({"detail": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

        jti = ott.get("jti")
        cache_key = f"ott:{jti}"
        if cache.get(cache_key):
            return Response({"detail": "Token already used"}, status=status.HTTP_400_BAD_REQUEST)
        cache.set(cache_key, 1, timeout=60)

        try:
            user = User.objects.get(id=ott["user_id"], is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
