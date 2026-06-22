# -*- coding: UTF-8 -*-
import secrets

from storages.backends.s3boto3 import S3Boto3Storage


class ErebusStorage(S3Boto3Storage):
    """
    Custom S3 storage class for erebus-ai file uploads.

    Uses the default Django object-storage bucket (DJANGO_AWS_*); only the
    no-overwrite behaviour is customised.
    """

    file_overwrite = False


def _get_upload_path(instance, filename):
    return f"{instance.uuid}/{filename}"


def _get_parsed_path(instance, filename):
    return f"{instance.parent.uuid}/parsed/v{instance.version}/{filename}"


def _create_hash(nbytes: int = 12) -> str:
    return secrets.token_urlsafe(nbytes)
