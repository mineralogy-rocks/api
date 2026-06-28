from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from store.views import FileUploadView
from store.views import SignedUrlView
from store.views import StoneColorViewSet
from store.views import StoneCutViewSet
from store.views import StoneTreatmentViewSet
from store.views import StoneViewSet
from store.views import StoreReportViewSet

app_name = "store"

router = DefaultRouter()
router.register("stones", StoneViewSet, basename="stone")
router.register("stone-colors", StoneColorViewSet, basename="stone-color")
router.register("stone-cuts", StoneCutViewSet, basename="stone-cut")
router.register("stone-treatments", StoneTreatmentViewSet, basename="stone-treatment")
router.register("reports", StoreReportViewSet, basename="report")

urlpatterns = [
    path("files/", FileUploadView.as_view(), name="file-upload"),
    path("files/<path:key>/signed-url/", SignedUrlView.as_view(), name="file-signed-url"),
    path("", include(router.urls)),
]
