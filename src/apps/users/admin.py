from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeForm
from .forms import UserCreationForm
from .models import Space
from .models import SpaceCollaborator
from .models import SpaceTag
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


@admin.register(SpaceTag)
class SpaceTagAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]
    ordering = ["name"]


class SpaceCollaboratorInline(admin.TabularInline):
    model = SpaceCollaborator
    extra = 0
    raw_id_fields = ["user"]
    fields = ["user", "permission_level", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "owner", "access", "created_at", "updated_at"]
    list_filter = ["access", "created_at"]
    search_fields = ["name", "owner__email", "owner__username"]
    raw_id_fields = ["owner"]
    filter_horizontal = ["tags"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [SpaceCollaboratorInline]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("name", "description", "owner")}),
        ("Access & Tags", {"fields": ("access", "tags")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SpaceCollaborator)
class SpaceCollaboratorAdmin(admin.ModelAdmin):
    list_display = ["id", "space", "user", "permission_level", "created_at"]
    list_filter = ["permission_level", "created_at"]
    search_fields = ["space__name", "user__email", "user__username"]
    raw_id_fields = ["space", "user"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
