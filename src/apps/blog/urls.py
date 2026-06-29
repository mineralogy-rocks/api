# -*- coding: UTF-8 -*-
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views as views

app_name = "blog"
router = DefaultRouter()

router.register(r"tag", views.TagViewSet, basename="tag")
router.register(r"category", views.CategoryViewSet, basename="category")
router.register(r"channel", views.ChannelViewSet, basename="channel")
router.register(r"author", views.AuthorViewSet, basename="author")
router.register(r"post", views.PostViewSet, basename="post")


urlpatterns = [
    path("files/", views.BlogImageUploadView.as_view(), name="file-upload"),
    path("", include(router.urls)),
]
