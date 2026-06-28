# -*- coding: UTF-8 -*-
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from users import views

app_name = "users"

router = DefaultRouter()
router.register(r"spaces", views.SpaceViewSet, basename="space")
router.register(r"invitations", views.InvitationViewSet, basename="invitation")
router.register(r"tags", views.UserTagViewSet, basename="tag")
router.register(r"password", views.PasswordResetViewSet, basename="password-reset")

urlpatterns = [
    path("me/", views.CurrentUserView.as_view(), name="current-user"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", include(router.urls)),
]
