# -*- coding: UTF-8 -*-
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class ErebusStorage(S3Boto3Storage):
    """
    Custom S3 storage class for erebus-ai file uploads
    """

    bucket_name = settings.EREBUS_STORAGE_BUCKET_NAME
    access_key = settings.EREBUS_ACCESS_KEY_ID
    secret_key = settings.EREBUS_SECRET_ACCESS_KEY
    endpoint_url = settings.EREBUS_S3_ENDPOINT_URL

    file_overwrite = False


def _get_upload_path(instance, filename):
    return f"{instance.uuid}/unprocessed/{filename}"


def _get_parsed_path(instance, filename):
    return f"{instance.uuid}/parsed/{filename}"
