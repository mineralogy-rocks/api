from django.core.exceptions import ValidationError
from django.db.models import Max
from django.db.models import Min
from django.http import HttpResponse
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
from store.filters import ReportFilter
from store.filters import StoneFilter
from store.models import Report
from store.models import Stone
from store.models import StoneColor
from store.models import StoneCut
from store.models import StoneTreatment
from store.pdf import build_qr_sheet_pdf
from store.pdf import build_report_pdf
from store.serializers import ReportAdminSerializer
from store.serializers import ReportPublicSerializer
from store.serializers import StoneAdminSerializer
from store.serializers import StoneColorSerializer
from store.serializers import StoneCutSerializer
from store.serializers import StonePublicDetailSerializer
from store.serializers import StonePublicListSerializer
from store.serializers import StoneTreatmentSerializer
from store.storage import signed_url
from store.storage import store_file
from users.authentication import CsrfExemptSessionAuthentication
from users.permissions import IsStaff
from users.permissions import IsStaffOrReadOnly


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


class StaffScopedMixin:
    def _is_staff(self):
        user = getattr(self.request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)


class StoreLookupViewSet(ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name"]
    ordering_fields = ["name", "id", "created_at"]
    ordering = ["name"]


class StoneColorViewSet(StoreLookupViewSet):
    queryset = StoneColor.objects.all()
    serializer_class = StoneColorSerializer


class StoneCutViewSet(StoreLookupViewSet):
    queryset = StoneCut.objects.all()
    serializer_class = StoneCutSerializer


class StoneTreatmentViewSet(StoreLookupViewSet):
    queryset = StoneTreatment.objects.all()
    serializer_class = StoneTreatmentSerializer


class StoneViewSet(StaffScopedMixin, ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    filterset_class = StoneFilter
    queryset = Stone.objects.all()
    search_fields = ["name", "description", "mineral", "country", "item_number"]
    ordering_fields = ["created_at", "selling_price", "weight_carats", "name", "sold_price", "country"]
    ordering = ["-created_at"]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self._is_staff():
            queryset = queryset.filter(is_selling=True)
        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=self.request)
        return queryset

    def get_serializer_class(self):
        if self._is_staff():
            return StoneAdminSerializer
        if self.action == "retrieve":
            return StonePublicDetailSerializer
        return StonePublicListSerializer

    def _facet_queryset(self):
        qs = Stone.objects.all()
        if not self._is_staff():
            qs = qs.filter(is_selling=True)
        return qs

    @action(detail=False, methods=["post"], url_path="bulk-delete", permission_classes=[IsStaff])
    def bulk_delete(self, request):
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"detail": "ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(ids) > 200:
            return Response(
                {"detail": "ids must contain at most 200 items"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = Stone.objects.filter(id__in=ids)
        try:
            count = queryset.count()
        except (ValidationError, ValueError):
            return Response(
                {"detail": "ids must be valid identifiers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset.delete()
        return Response({"deleted": count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="facets")
    def facets(self, request):
        queryset = self._facet_queryset()

        price = queryset.filter(selling_price__isnull=False).aggregate(
            min=Min("selling_price"),
            max=Max("selling_price"),
        )
        weight = queryset.filter(weight_carats__isnull=False).aggregate(
            min=Min("weight_carats"),
            max=Max("weight_carats"),
        )

        price_range = None
        if price["min"] is not None:
            price_range = {"min": float(price["min"]), "max": float(price["max"])}

        weight_range = None
        if weight["min"] is not None:
            weight_range = {"min": float(weight["min"]), "max": float(weight["max"])}

        color_ids = queryset.filter(color_id__isnull=False).values_list("color_id", flat=True).distinct()
        cut_ids = queryset.filter(cut_id__isnull=False).values_list("cut_id", flat=True).distinct()

        colors = [
            {"id": color.id, "name": color.name, "hex": color.hex}
            for color in StoneColor.objects.filter(id__in=color_ids).order_by("id")
        ]
        cuts = [{"id": cut.id, "name": cut.name} for cut in StoneCut.objects.filter(id__in=cut_ids).order_by("name")]

        return Response(
            {
                "priceRange": price_range,
                "weightRange": weight_range,
                "colors": colors,
                "cuts": cuts,
            },
            status=status.HTTP_200_OK,
        )


class StoreReportViewSet(StaffScopedMixin, ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    filterset_class = ReportFilter
    queryset = Report.objects.all()
    search_fields = ["title", "stone", "first_name", "last_name", "owner_email"]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self._is_staff():
            queryset = queryset.filter(public=True)
        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "setup_eager_loading"):
            queryset = serializer_class.setup_eager_loading(queryset=queryset, request=self.request)
        return queryset

    def get_serializer_class(self):
        if self._is_staff():
            return ReportAdminSerializer
        return ReportPublicSerializer

    @action(detail=True, methods=["patch"], url_path="toggle-public", permission_classes=[IsStaff])
    def toggle_public(self, request, pk=None):
        report = self.get_object()
        report.public = not report.public
        report.save(update_fields=["public", "updated_at"])
        serializer = ReportAdminSerializer(report, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="search", permission_classes=[IsStaff])
    def search_unlinked(self, request):
        query = request.query_params.get("q", "").strip()
        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except (TypeError, ValueError):
            limit = 20
        queryset = Report.objects.filter(linked_stone__isnull=True)
        if query:
            queryset = queryset.filter(title__icontains=query) | queryset.filter(stone__icontains=query)
        queryset = queryset.order_by("-created_at")[:limit]
        results = [
            {
                "id": str(report.id),
                "title": report.title,
                "stone": report.stone,
                "created_at": report.created_at,
            }
            for report in queryset
        ]
        return Response({"results": results}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        report = self.get_object()
        content = build_report_pdf(report, include_admin_fields=self._is_staff())
        filename = slugify(report.title) or "report"
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}.pdf"'
        return response

    @action(detail=False, methods=["get"], url_path="export-qr", permission_classes=[IsStaff])
    def export_qr(self, request):
        reports = Report.objects.filter(public=True).order_by("-created_at")
        content = build_qr_sheet_pdf(reports)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="report-qr-codes.pdf"'
        return response
