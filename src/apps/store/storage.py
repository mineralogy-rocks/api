from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

GEMS_LOCATION = "gems"


class _BaseGemsStorage(S3Boto3Storage):
    def __init__(self, **kwargs):
        kwargs.setdefault("bucket_name", settings.GEMS_S3_BUCKET)
        kwargs.setdefault("endpoint_url", settings.GEMS_S3_ENDPOINT_URL)
        kwargs.setdefault("access_key", settings.GEMS_S3_ACCESS_KEY)
        kwargs.setdefault("secret_key", settings.GEMS_S3_SECRET_KEY)
        kwargs.setdefault("region_name", settings.GEMS_S3_REGION)
        kwargs.setdefault("location", GEMS_LOCATION)
        kwargs.setdefault("file_overwrite", False)
        super().__init__(**kwargs)


class PublicGemsStorage(_BaseGemsStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("querystring_auth", False)
        kwargs.setdefault("default_acl", "public-read")
        super().__init__(**kwargs)


class PrivateGemsStorage(_BaseGemsStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", settings.GEMS_SIGNED_URL_EXPIRE)
        kwargs.setdefault("default_acl", None)
        super().__init__(**kwargs)


public_storage = PublicGemsStorage()
private_storage = PrivateGemsStorage()


def store_public(file, name):
    """Save `file` under the gems/ prefix as a public object; return its name."""
    return public_storage.save(name, file)


def store_private(file, name):
    """Save `file` under the gems/ prefix as a private object; return its name."""
    return private_storage.save(name, file)


def public_url(name):
    """Return a stable, unsigned URL for a public gems file."""
    return public_storage.url(name)


def signed_url(name):
    """Return a short-lived, signed URL for a private gems file."""
    return private_storage.url(name)
