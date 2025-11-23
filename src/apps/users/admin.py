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
    raw_id_fields = ["user", "invited_by"]
    fields = [
        "user",
        "invited_email",
        "invited_by",
        "permission_level",
        "is_pending",
        "is_accepted",
        "is_revoked",
        "invitation_sent_at",
        "invitation_expires_at",
        "created_at",
    ]
    readonly_fields = [
        "invited_email",
        "invited_by",
        "is_pending",
        "is_accepted",
        "is_revoked",
        "invitation_sent_at",
        "invitation_expires_at",
        "created_at",
    ]


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
    list_display = [
        "id",
        "space",
        "user",
        "invited_email",
        "invited_by",
        "permission_level",
        "is_pending",
        "is_accepted",
        "is_revoked",
        "invitation_expires_at",
        "created_at",
    ]
    list_filter = ["permission_level", "is_pending", "is_accepted", "is_revoked", "created_at"]
    search_fields = [
        "space__name",
        "user__email",
        "user__username",
        "invited_email",
        "invited_by__email",
        "invited_by__username",
    ]
    raw_id_fields = ["space", "user", "invited_by"]
    readonly_fields = [
        "invited_by",
        "is_revoked",
        "invitation_token",
        "invitation_sent_at",
        "invitation_expires_at",
        "created_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("space", "user", "invited_email", "invited_by", "permission_level")}),
        (
            "Invitation Status",
            {
                "fields": (
                    "is_pending",
                    "is_accepted",
                    "is_revoked",
                    "invitation_token",
                    "invitation_sent_at",
                    "invitation_expires_at",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    actions = ["resend_invitations"]

    @admin.action(description="Resend invitation emails")
    def resend_invitations(self, request, queryset):
        from django.utils import timezone

        from users.services import calculate_expiration_date
        from users.services import generate_invitation_token
        from users.services import send_invitation_email

        count = 0
        for collaboration in queryset.filter(is_pending=True, is_accepted=None):
            token = generate_invitation_token()
            collaboration.invitation_token = token
            collaboration.invitation_sent_at = timezone.now()
            collaboration.invitation_expires_at = calculate_expiration_date(days=7)
            collaboration.save()

            permission_display = dict(SpaceCollaborator.PERMISSION_CHOICES).get(collaboration.permission_level)

            send_invitation_email(
                email=collaboration.invited_email or collaboration.user.email,
                space=collaboration.space,
                inviter=collaboration.space.owner,
                token=token,
                permission_level_display=permission_display,
                is_new_user=not collaboration.user.is_active,
            )
            count += 1

        self.message_user(request, f"{count} invitation(s) resent successfully.")
