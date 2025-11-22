# -*- coding: UTF-8 -*-
from django.urls import path

from users import views

app_name = "users"

urlpatterns = [
    path("me/", views.CurrentUserView.as_view(), name="current-user"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]
