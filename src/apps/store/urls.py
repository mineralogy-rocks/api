from django.urls import path

from store.views import FileUploadView
from store.views import PingView
from store.views import SignedUrlView
from store.views import StoreMeView

app_name = "store"

urlpatterns = [
    path("ping/", PingView.as_view(), name="ping"),
    path("me/", StoreMeView.as_view(), name="me"),
    path("files/", FileUploadView.as_view(), name="file-upload"),
    path("files/<path:key>/signed-url/", SignedUrlView.as_view(), name="file-signed-url"),
]
