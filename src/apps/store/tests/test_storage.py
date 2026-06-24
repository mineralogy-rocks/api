from django.test import SimpleTestCase

from store.storage import signed_url


class StoreStorageUrlTests(SimpleTestCase):
    def test_signed_url_is_namespaced_and_signed(self):
        url = signed_url("sample.jpg")
        self.assertIn("store/sample.jpg", url)
        self.assertTrue("X-Amz-Signature" in url or "Signature=" in url)
        self.assertTrue("X-Amz-Expires" in url or "Expires=" in url)
