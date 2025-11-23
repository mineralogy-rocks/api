# -*- coding: UTF-8 -*-
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
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
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import Space
from users.models import SpaceCollaborator
from users.models import User
from users.permissions import IsSpaceOwnerOrCollaborator
from users.serializers import InvitationResponseSerializer
from users.serializers import PendingInvitationSerializer
from users.serializers import SentInvitationSerializer
from users.serializers import SpaceCollaboratorSerializer
from users.serializers import SpaceCreateSerializer
from users.serializers import SpaceInvitationSerializer
from users.serializers import SpaceSerializer
from users.serializers import SpaceUpdateSerializer
from users.serializers import UserSerializer
from users.serializers import UserUpdateSerializer
from users.services import activate_invited_user
from users.services import calculate_expiration_date
from users.services import generate_invitation_token
from users.services import send_invitation_email
from users.services import validate_invitation_token


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


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

    if not username or not password:
        return Response(
            {"detail": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
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

    def get_queryset(self):
        queryset = Space.objects.all()
        serializer_class = self.get_serializer_class()

        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return SpaceCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return SpaceUpdateSerializer
        return SpaceSerializer

    @action(detail=False, methods=["get"], url_path="my-spaces")
    def my_spaces(self, request):
        user = request.user
        spaces = Space.objects.filter(
            Q(owner=user)
            | Q(
                collaborators__user=user,
                collaborators__is_accepted=True,
                collaborators__is_revoked=False,
            )
        ).distinct()

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            spaces = serializer_class.setup_eager_loading(spaces)

        serializer = SpaceSerializer(spaces, many=True)
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

        serializer = SpaceSerializer(space)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvitationViewSet(viewsets.GenericViewSet):
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        authentication_classes=[SessionAuthentication],
    )
    def pending(self, request):
        user = request.user
        invitations = SpaceCollaborator.objects.filter(
            user=user,
            is_pending=True,
            is_accepted=None,
        ).select_related("space", "space__owner")

        serializer = PendingInvitationSerializer(invitations, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        authentication_classes=[SessionAuthentication],
    )
    def sent(self, request):
        user = request.user
        invitations = (
            SpaceCollaborator.objects.filter(
                invited_by=user,
            )
            .select_related("space", "user")
            .order_by("-invitation_sent_at")
        )

        serializer = SentInvitationSerializer(invitations, many=True)
        return Response(serializer.data)

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

        activate_invited_user(invitation.user, invitation)

        return Response(
            {
                "detail": "Invitation accepted successfully",
                "space_id": invitation.space.id,
                "space_name": invitation.space.name,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        authentication_classes=[CsrfExemptSessionAuthentication],
        url_path="decline",
    )
    def decline_invitation(self, request):
        serializer = InvitationResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        invitation, error = validate_invitation_token(token)

        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        invitation.is_pending = False
        invitation.is_accepted = False
        invitation.save()

        return Response(
            {"detail": "Invitation declined successfully"},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        authentication_classes=[SessionAuthentication],
    )
    def revoke(self, request):
        collaborator_id = request.data.get("collaborator_id")

        if not collaborator_id:
            return Response(
                {"detail": "collaborator_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            collaboration = SpaceCollaborator.objects.select_related("space", "invited_by").get(id=collaborator_id)
        except SpaceCollaborator.DoesNotExist:
            return Response(
                {"detail": "Collaboration not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        space = collaboration.space

        can_revoke = False
        if space.owner == user:
            can_revoke = True
        else:
            try:
                user_collaboration = SpaceCollaborator.objects.get(
                    space=space,
                    user=user,
                    is_pending=False,
                    is_accepted=True,
                    is_revoked=False,
                )
                if user_collaboration.permission_level in [
                    SpaceCollaborator.PERMISSION_SUPERADMIN,
                    SpaceCollaborator.PERMISSION_ADMIN,
                ]:
                    can_revoke = True
                elif collaboration.invited_by == user and user_collaboration:
                    can_revoke = True
            except SpaceCollaborator.DoesNotExist:
                pass

        if not can_revoke:
            return Response(
                {"detail": "You do not have permission to revoke this invitation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        collaboration.is_revoked = True
        collaboration.save()

        return Response(
            {"detail": "Invitation revoked successfully"},
            status=status.HTTP_200_OK,
        )
