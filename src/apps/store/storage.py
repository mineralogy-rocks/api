from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

STORE_LOCATION = "store"
GEMS_PUBLIC_LOCATION = "gems"


class StoreStorage(S3Boto3Storage):
    """
    Store files on the shared Hetzner bucket (DJANGO_AWS_*) under the store/
    prefix.

    The bucket stays private; every read is mediated by the backend, which
    issues a short-lived signed URL after its own availability/permission
    checks. Bucket, endpoint and credentials are inherited from the AWS_*
    settings, so only the store-specific behaviour is set here.
    """

    location = STORE_LOCATION
    default_acl = None
    querystring_auth = True
    file_overwrite = False

    def __init__(self, **kwargs):
        kwargs.setdefault("querystring_expire", settings.STORE_SIGNED_URL_EXPIRE)
        super().__init__(**kwargs)


class GemsPublicStorage(S3Boto3Storage):
    """
    Serve stone images from the shared bucket under the gems/ prefix with
    stable, unsigned public URLs.

    Unlike StoreStorage, reads are not mediated by the backend: the URL is
    built locally and never expires, so the same path can be cached and
    embedded directly in the storefront.
    """

    location = GEMS_PUBLIC_LOCATION
    default_acl = None
    querystring_auth = False
    file_overwrite = False


storage = StoreStorage()
public_storage = GemsPublicStorage()


def store_file(file, name):
    """Save `file` under the store/ prefix; return its stored name."""
    return storage.save(name, file)


def signed_url(name):
    """Return a short-lived, signed URL for a store file."""
    return storage.url(name)


def public_url(name):
    """Return a stable public URL for a gems public asset (stone image)."""
    if not name:
        return None
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return public_storage.url(name)
