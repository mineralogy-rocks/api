# -*- coding: UTF-8 -*-
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views as views

app_name = "erebus"
router = DefaultRouter()

router.register(r"queue", views.QueueViewSet, basename="queue")
router.register(r"chunk", views.ChunkViewSet, basename="chunk")
router.register(r"prompt", views.PromptViewSet, basename="prompt")
router.register(r"component", views.ComponentViewSet, basename="component")
router.register(r"ai-response", views.AIResponseViewSet, basename="ai-response")

urlpatterns = [
    path("", include(router.urls)),
]
