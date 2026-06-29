from blog.storage import public_url
from django.test import SimpleTestCase
from django.test import override_settings

LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "blog_public": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "/tmp/test-media/blog_public",
            "base_url": "http://testserver/media/blog_public/",
        },
    },
}

S3_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "blog_public": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "blog_public",
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    },
}


class BlogStorageUrlTests(SimpleTestCase):
    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_public_url_uses_configured_local_public_storage(self):
        self.assertEqual(public_url("sample.jpg"), "http://testserver/media/blog_public/sample.jpg")

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_public_url_preserves_absolute_urls(self):
        self.assertEqual(public_url("https://example.test/sample.jpg"), "https://example.test/sample.jpg")

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_public_url_returns_none_for_empty(self):
        self.assertIsNone(public_url(""))
        self.assertIsNone(public_url(None))

    @override_settings(STORAGES=S3_STORAGES)
    def test_public_url_is_namespaced_and_unsigned_for_s3(self):
        url = public_url("sample.jpg")
        self.assertIn("blog_public/sample.jpg", url)
        self.assertNotIn("X-Amz-Signature", url)
        self.assertNotIn("Signature=", url)
