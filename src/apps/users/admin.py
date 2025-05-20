from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeForm
from .forms import UserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = [
        "username",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "last_login",
    ]

    ordering = ["-id"]
    search_fields = ["username", "email"]
