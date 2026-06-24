from django.urls import path

from store.views import PingView

app_name = "store"

urlpatterns = [
    path("ping/", PingView.as_view(), name="ping"),
]
