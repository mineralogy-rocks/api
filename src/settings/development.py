# -*- coding: UTF-8 -*-
import sys

from .base import *

TESTING = "test" in sys.argv

if not TESTING:
    INSTALLED_APPS += [
        "debug_toolbar",
    ]

    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

INTERNAL_IPS = [
    "127.0.0.1",
    "0.0.0.0",
    "localhost",
]

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "../.tmp/messages"

DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda _request: DEBUG}

CACHE_TTL = 10  # Set cache time to 5 seconds in dev mode

STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", default="/app/static")
MEDIA_ROOT = os.environ.get("DJANGO_MEDIA_ROOT", default="/app/media")

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
