from blog.constants import BLOG_PREFIX
from core.storage import signed_url
from django.test import SimpleTestCase
from django.test import override_settings

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


class BlogStorageUrlTests(SimpleTestCase):
    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_uses_configured_local_blog_storage(self):
        self.assertEqual(signed_url("sample.jpg", prefix=BLOG_PREFIX), "http://testserver/media/blog/sample.jpg")

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_preserves_absolute_urls(self):
        self.assertEqual(
            signed_url("https://example.test/sample.jpg", prefix=BLOG_PREFIX), "https://example.test/sample.jpg"
        )

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_signed_url_returns_none_for_empty(self):
        self.assertIsNone(signed_url("", prefix=BLOG_PREFIX))
        self.assertIsNone(signed_url(None, prefix=BLOG_PREFIX))

    @override_settings(STORAGES=S3_STORAGES)
    def test_signed_url_is_namespaced_and_signed_for_s3(self):
        url = signed_url("sample.jpg", prefix=BLOG_PREFIX)
        self.assertIn("blog/sample.jpg", url)
        self.assertTrue("X-Amz-Signature" in url or "Signature=" in url)
        self.assertTrue("X-Amz-Expires" in url or "Expires=" in url)
