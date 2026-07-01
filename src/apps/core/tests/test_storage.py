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


class CoreStorageSignedUrlTests(SimpleTestCase):
    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_prefixes_name_under_given_prefix(self):
        self.assertEqual(
            signed_url("sample.jpg", prefix="foo/bar"),
            "http://testserver/media/foo/bar/sample.jpg",
        )

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_preserves_names_already_under_the_prefix_root(self):
        self.assertEqual(
            signed_url("foo/baz/sample.jpg", prefix="foo/bar"),
            "http://testserver/media/foo/baz/sample.jpg",
        )

    @override_settings(STORAGES=LOCAL_STORAGES)
    def test_preserves_absolute_urls(self):
        self.assertEqual(
            signed_url("https://example.test/sample.jpg", prefix="foo"),
            "https://example.test/sample.jpg",
        )

    def test_returns_none_for_empty(self):
        self.assertIsNone(signed_url("", prefix="foo"))
        self.assertIsNone(signed_url(None, prefix="foo"))
