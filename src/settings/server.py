# -*- coding: UTF-8 -*-
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

sentry_sdk.init(
    dsn=os.environ.get("DJANGO_SENTRY_DSN", default=None),
    environment=os.environ.get("DJANGO_SENTRY_ENV", default=""),
    integrations=[DjangoIntegration()],
)

CACHE_TTL = 60 * 15  # Set cache time to 15 minutes

AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

AWS_LOCATION = "static"
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("SENDGRID_API_KEY")
EMAIL_PORT = os.environ.get("DJANGO_EMAIL_PORT")
EMAIL_USE_TLS = True

STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

STATIC_URL = "{}/{}/".format(AWS_S3_ENDPOINT_URL, AWS_LOCATION)
