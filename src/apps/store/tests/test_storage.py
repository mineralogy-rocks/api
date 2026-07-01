from core.storage import signed_url
from django.test import SimpleTestCase
from django.test import override_settings
from store.constants import STORE_REPORTS_PREFIX
from store.constants import STORE_STONES_PREFIX

LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "media": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "/tmp/test-media",
            "base_url": "http://testserver/media/",
        },
    },
}

S3_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "media": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 3600,
            "file_overwrite": False,
        },
    },
}


class StoreStorageUrlTests(SimpleTestCase):
    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_uses_configured_local_report_storage(self):
        self.assertEqual(
            signed_url("sample.jpg", prefix=STORE_REPORTS_PREFIX), "http://testserver/media/store/reports/sample.jpg"
        )

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_uses_configured_local_stone_storage(self):
        self.assertEqual(
            signed_url("sample.jpg", prefix=STORE_STONES_PREFIX),
            "http://testserver/media/store/stones/sample.jpg",
        )

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_preserves_absolute_urls(self):
        self.assertEqual(
            signed_url("https://example.test/sample.jpg", prefix=STORE_REPORTS_PREFIX),
            "https://example.test/sample.jpg",
        )

    @override_settings(STORAGES=S3_STORAGES)
    def test_signed_url_is_namespaced_and_signed_for_s3(self):
        url = signed_url("sample.jpg", prefix=STORE_REPORTS_PREFIX)
        self.assertIn("store/reports/sample.jpg", url)
        self.assertTrue("X-Amz-Signature" in url or "Signature=" in url)
        self.assertTrue("X-Amz-Expires" in url or "Expires=" in url)

    @override_settings(STORAGES=S3_STORAGES)
    def test_stone_signed_url_is_namespaced_and_signed_for_s3(self):
        url = signed_url("sample.jpg", prefix=STORE_STONES_PREFIX)
        self.assertIn("store/stones/sample.jpg", url)
        self.assertTrue("X-Amz-Signature" in url or "Signature=" in url)
        self.assertTrue("X-Amz-Expires" in url or "Expires=" in url)
