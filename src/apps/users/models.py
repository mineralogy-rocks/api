# -*- coding: UTF-8 -*-
from django.contrib.auth.models import AbstractUser

""" STEP 1: set AUTH_USER_MODEL in settings, deploy to production and execute these sql scripts BEFORE the deploy occurs:
    INSERT INTO django_migrations (app, name, applied) VALUES ('users', '0001_initial', CURRENT_TIMESTAMP);
    UPDATE django_content_type SET app_label = 'users' WHERE app_label = 'auth' and model = 'user';
    update auth_user set email = 'marko.bermanec@gmail.com' where username = 'marko.bermanec';

    STEP 2: uncomment code, create a migration and run a normal migration again.

    Notes: here's a quick ref: https://www.caktusgroup.com/blog/2019/04/26/how-switch-custom-django-user-model-mid-project/
"""


class User(AbstractUser):
    class Meta:
        db_table = "auth_user"


#
# class CustomUserManager(BaseUserManager):
#     use_in_migrations = True
#
#     def _create_user(self, email, password, **extra_fields):
#         if not email:
#             raise ValueError("The given email must be set")
#         email = self.normalize_email(email)
#         user = self.model(email=email, **extra_fields)
#         user.set_password(password)
#         user.save(using=self._db)
#         return user
#
#     def create_user(self, email=None, password=None, **extra_fields):
#         extra_fields.setdefault("is_staff", False)
#         extra_fields.setdefault("is_superuser", False)
#         extra_fields.setdefault("is_active", True)
#         return self._create_user(email, password, **extra_fields)
#
#     def create_superuser(self, email=None, password=None, **extra_fields):
#         extra_fields.setdefault("is_staff", True)
#         extra_fields.setdefault("is_superuser", True)
#         extra_fields.setdefault("is_active", True)
#
#         if extra_fields.get("is_staff") is not True:
#             raise ValueError("Superuser must have is_staff=True.")
#         if extra_fields.get("is_superuser") is not True:
#             raise ValueError("Superuser must have is_superuser=True.")
#
#         return self._create_user(email, password, **extra_fields)
#
#
# class User(PermissionsMixin, AbstractBaseUser):
#
#     username = models.CharField(
#         _("username"),
#         max_length=150,
#         null=True,
#         blank=True,
#     )
#     first_name = models.CharField(_("first name"), max_length=150, blank=True)
#     last_name = models.CharField(_("last name"), max_length=150, blank=True)
#
#     email = models.EmailField(_("email address"), unique=True)
#
#     is_staff = models.BooleanField(
#         _("staff status"),
#         default=False,
#         help_text=_("Designates whether the user can log into this admin site."),
#     )
#     is_active = models.BooleanField(
#         _("active"),
#         default=True,
#         help_text=_(
#             "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
#         ),
#     )
#
#     date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
#
#     objects = CustomUserManager()
#
#     USERNAME_FIELD = "email"
#
#     class Meta:
#         db_table = "auth_user"
#         verbose_name = _("User")
#         verbose_name_plural = _("Users")
#
#     def __str__(self):
#         return self.email
#
#     def clean(self):
#         super().clean()
#         self.email = self.__class__.objects.normalize_email(self.email)
#
#     def get_full_name(self):
#         """
#         Return the first_name plus the last_name, with a space in between.
#         """
#         full_name = "%s %s" % (self.first_name, self.last_name)
#         return full_name.strip()
#
#     def get_short_name(self):
#         """Return the short name for the user."""
#         return self.first_name
#
#     def email_user(self, subject, message, from_email=None, **kwargs):
#         send_email(subject, message, from_email, [self.email], **kwargs)
