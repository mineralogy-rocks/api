from django.test import SimpleTestCase
from django.test import override_settings
from store.storage import public_url
from store.storage import signed_url

LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "store_private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "/tmp/test-media/store_private",
            "base_url": "http://testserver/media/store_private/",
        },
    },
    "store_public": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "/tmp/test-media/store_public",
            "base_url": "http://testserver/media/store_public/",
        },
    },
}

S3_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "store_private": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "store_private",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 3600,
            "file_overwrite": False,
        },
    },
    "store_public": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "store_public",
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    },
}


class StoreStorageUrlTests(SimpleTestCase):
    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_uses_configured_local_store_storage(self):
        self.assertEqual(signed_url("sample.jpg"), "http://testserver/media/store_private/sample.jpg")

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_public_url_uses_configured_local_public_storage(self):
        self.assertEqual(public_url("sample.jpg"), "http://testserver/media/store_public/sample.jpg")

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_public_url_preserves_absolute_urls(self):
        self.assertEqual(public_url("https://example.test/sample.jpg"), "https://example.test/sample.jpg")

    @override_settings(STORAGES=S3_STORAGES)
    def test_signed_url_is_namespaced_and_signed_for_s3(self):
        url = signed_url("sample.jpg")
        self.assertIn("store_private/sample.jpg", url)
        self.assertTrue("X-Amz-Signature" in url or "Signature=" in url)
        self.assertTrue("X-Amz-Expires" in url or "Expires=" in url)
