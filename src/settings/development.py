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
STORE_LOCAL_MEDIA_URL = os.environ.get("DJANGO_STORE_LOCAL_MEDIA_URL") or "http://api.mineralogy.rocks.local/media/"

STORAGES["default"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {
        "location": MEDIA_ROOT,
        "base_url": MEDIA_URL,
    },
}
STORAGES["store_private"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {
        "location": os.path.join(MEDIA_ROOT, "store_private"),
        "base_url": f"{STORE_LOCAL_MEDIA_URL.rstrip('/')}/store_private/",
    },
}
STORAGES["store_public"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {
        "location": os.path.join(MEDIA_ROOT, "store_public"),
        "base_url": f"{STORE_LOCAL_MEDIA_URL.rstrip('/')}/store_public/",
    },
}
STORAGES["blog_public"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {
        "location": os.path.join(MEDIA_ROOT, "blog_public"),
        "base_url": f"{STORE_LOCAL_MEDIA_URL.rstrip('/')}/blog_public/",
    },
}
