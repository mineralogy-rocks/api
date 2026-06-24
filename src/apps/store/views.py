from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


class PingView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        paginator = LimitOffsetPagination()
        data = [{"status": "ok", "service": "store"}]
        page = paginator.paginate_queryset(data, request, view=self)
        return paginator.get_paginated_response(page)
