# -*- coding: UTF-8 -*-
from core.models.base import BaseModel
from core.models.base import Creatable
from core.models.base import Nameable
from core.models.base import Updatable
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

""" STEP 1: set AUTH_USER_MODEL in settings, deploy to production and execute these sql scripts BEFORE the deploy occurs:
    INSERT INTO django_migrations (app, name, applied) VALUES ('users', '0001_initial', CURRENT_TIMESTAMP);
    UPDATE django_content_type SET app_label = 'users' WHERE app_label = 'auth' and model = 'user';
    update auth_user set email = 'marko.bermanec@gmail.com' where username = 'marko.bermanec';

    STEP 2: uncomment code, create a migration and run a normal migration again.

    Notes: here's a quick ref: https://www.caktusgroup.com/blog/2019/04/26/how-switch-custom-django-user-model-mid-project/
"""


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(PermissionsMixin, AbstractBaseUser):
    username = models.CharField(
        _("username"),
        max_length=150,
        null=True,
        blank=True,
    )
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    linkedin_url = models.URLField(_("LinkedIn URL"), max_length=200, blank=True)

    email = models.EmailField(_("email address"), unique=True)

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_(
            "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
        ),
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"

    class Meta:
        db_table = "auth_user"
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)


class UserTag(BaseModel, Creatable, Updatable):
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name_encrypted = models.TextField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User Tag"
        verbose_name_plural = "User Tags"

    def __str__(self):
        return f"Tag {self.id} ({self.user.email})"


class Space(BaseModel, Nameable, Creatable, Updatable):
    ACCESS_FULL_PUBLIC = 0
    ACCESS_SEMI_PUBLIC = 1
    ACCESS_PRIVATE = 2

    ACCESS_CHOICES = (
        (ACCESS_FULL_PUBLIC, _("Full Public")),
        (ACCESS_SEMI_PUBLIC, _("Semi Public")),
        (ACCESS_PRIVATE, _("Private")),
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_spaces",
    )
    description = models.TextField(null=True, blank=True)
    access = models.IntegerField(
        choices=ACCESS_CHOICES,
        default=ACCESS_FULL_PUBLIC,
        null=False,
    )
    tags = models.ManyToManyField(UserTag, related_name="spaces", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Space"
        verbose_name_plural = "Spaces"

    def __str__(self):
        return self.name


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Password reset token for {self.user.email}"


class SpaceCollaborator(BaseModel, Creatable):
    PERMISSION_VIEWER = 0
    PERMISSION_ADMIN = 1
    PERMISSION_SUPERADMIN = 2

    PERMISSION_CHOICES = (
        (PERMISSION_VIEWER, _("Viewer")),
        (PERMISSION_ADMIN, _("Admin")),
        (PERMISSION_SUPERADMIN, _("Superadmin")),
    )

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="collaborators",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="space_collaborations",
        null=True,
        blank=True,
    )
    permission_level = models.IntegerField(
        choices=PERMISSION_CHOICES,
        null=False,
    )

    is_pending = models.BooleanField(default=True)
    is_accepted = models.BooleanField(null=True, blank=True, default=None)
    is_revoked = models.BooleanField(default=False)
    invitation_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    invited_email = models.EmailField(null=True, blank=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="sent_invitations",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Space Collaborator"
        verbose_name_plural = "Space Collaborators"
        constraints = [
            models.UniqueConstraint(
                fields=["space", "user"],
                condition=models.Q(is_accepted=True),
                name="unique_accepted_collaborator",
            )
        ]

    def __str__(self):
        email = self.user.email if self.user else self.invited_email
        status = "Pending" if self.is_pending else "Accepted"
        return f"{email} - {self.space.name} ({self.get_permission_level_display()}) - {status}"
