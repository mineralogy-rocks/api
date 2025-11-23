# -*- coding: UTF-8 -*-
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.db.models import Q
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
from users.serializers import SpaceCollaboratorSerializer
from users.serializers import SpaceCreateSerializer
from users.serializers import SpaceSerializer
from users.serializers import SpaceUpdateSerializer
from users.serializers import UserSerializer
from users.serializers import UserUpdateSerializer


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
    authentication_classes = [CsrfExemptSessionAuthentication]
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

    @action(detail=False, methods=["get"])
    def my_spaces(self, request):
        user = request.user
        spaces = Space.objects.filter(Q(owner=user) | Q(collaborators__user=user)).distinct()

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            spaces = serializer_class.setup_eager_loading(spaces)

        serializer = SpaceSerializer(spaces, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_collaborator(self, request, pk=None):
        space = self.get_object()
        user_id = request.data.get("user_id")
        permission_level = request.data.get("permission_level")

        if not user_id or permission_level is None:
            return Response(
                {"detail": "user_id and permission_level are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if space.owner.id == user_id:
            return Response(
                {"detail": "Owner cannot be added as collaborator"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SpaceCollaboratorSerializer(
            data={
                "user_id": user_id,
                "permission_level": permission_level,
            },
            context={"request": request},
        )

        if serializer.is_valid():
            try:
                serializer.save(space=space)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
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

    @action(detail=True, methods=["post"])
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

    @action(detail=True, methods=["post"])
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
