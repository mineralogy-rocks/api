# -*- coding: UTF-8 -*-
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *

INSTALLED_APPS += [
    "ddtrace.contrib.django",
]

sentry_sdk.init(
    dsn=os.environ.get("DJANGO_SENTRY_DSN", default=None),
    environment=os.environ.get("DJANGO_SENTRY_ENV", default=""),
    integrations=[DjangoIntegration()],
)

CACHE_TTL = 60 * 15  # Set cache time to 15 minutes

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

AWS_LOCATION = "static"
AWS_DEFAULT_ACL = "public-read"
AWS_QUERYSTRING_AUTH = False

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("SENDGRID_API_KEY")
EMAIL_PORT = os.environ.get("DJANGO_EMAIL_PORT")
EMAIL_USE_TLS = True

STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

STATIC_URL = "{}/{}/".format(AWS_S3_ENDPOINT_URL, AWS_LOCATION)
