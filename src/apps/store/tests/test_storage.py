from django.test import SimpleTestCase

from store.storage import public_url
from store.storage import signed_url


class GemsStorageUrlTests(SimpleTestCase):
    def test_public_url_is_stable_and_unsigned(self):
        url = public_url("sample.jpg")
        self.assertIn("gems/sample.jpg", url)
        self.assertNotIn("X-Amz-Signature", url)

    def test_private_url_is_signed_and_expiring(self):
        url = signed_url("sample.jpg")
        self.assertIn("gems/sample.jpg", url)
        self.assertIn("X-Amz-Signature", url)
        self.assertTrue("X-Amz-Expires" in url or "Expires" in url)
