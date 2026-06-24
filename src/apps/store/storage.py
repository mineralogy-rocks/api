from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

STORE_LOCATION = "store"


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


storage = StoreStorage()


def store_file(file, name):
    """Save `file` under the store/ prefix; return its stored name."""
    return storage.save(name, file)


def signed_url(name):
    """Return a short-lived, signed URL for a store file."""
    return storage.url(name)
