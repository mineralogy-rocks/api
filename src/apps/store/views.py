from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.authentication import CsrfExemptSessionAuthentication
from users.permissions import IsStaff

from store.storage import signed_url
from store.storage import store_file


class PingView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        paginator = LimitOffsetPagination()
        data = [{"status": "ok", "service": "store"}]
        page = paginator.paginate_queryset(data, request, view=self)
        return paginator.get_paginated_response(page)


class StoreMeView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "is_staff": user.is_staff,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_200_OK,
        )


class FileUploadView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsStaff]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file is required"}, status=status.HTTP_400_BAD_REQUEST)
        stored_name = store_file(file, file.name)
        return Response(
            {"name": stored_name, "url": signed_url(stored_name)},
            status=status.HTTP_201_CREATED,
        )


class SignedUrlView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsStaff]

    def get(self, request, key):
        return Response({"url": signed_url(key)}, status=status.HTTP_200_OK)
