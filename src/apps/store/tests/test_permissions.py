from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class FileUploadPermissionTests(APITestCase):
    def setUp(self):
        self.url = "/store/files/"
        self.non_staff_user = User.objects.create_user(email="regular@example.com", password="pass123")
        self.non_staff_user.is_active = True
        self.non_staff_user.is_staff = False
        self.non_staff_user.save()

        self.staff_user = User.objects.create_user(email="staff@example.com", password="pass123")
        self.staff_user.is_active = True
        self.staff_user.is_staff = True
        self.staff_user.save()

    def test_anonymous_returns_403(self):
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_login(self.non_staff_user)
        file = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        response = self.client.post(self.url, {"file": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("store.views.store_file")
    @patch("store.views.signed_url")
    def test_staff_returns_201(self, mock_signed_url, mock_store_file):
        mock_store_file.return_value = "store/reports/test.txt"
        mock_signed_url.return_value = "https://example.com/signed/test.txt"

        self.client.force_login(self.staff_user)
        file = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        response = self.client.post(self.url, {"file": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("name", response.data)
        self.assertIn("url", response.data)
        self.assertEqual(mock_store_file.call_args.kwargs["prefix"], "store/reports")

    @patch("store.views.store_file")
    @patch("store.views.signed_url")
    def test_staff_stone_upload_uses_stone_prefix(self, mock_signed_url, mock_store_file):
        mock_store_file.return_value = "store/stones/test.jpg"
        mock_signed_url.return_value = "https://example.com/signed/store/stones/test.jpg"

        self.client.force_login(self.staff_user)
        file = SimpleUploadedFile("test.jpg", b"hello", content_type="image/jpeg")
        response = self.client.post("/store/files/stones/", {"file": file}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_store_file.assert_called_once()
        self.assertEqual(mock_store_file.call_args.kwargs["prefix"], "store/stones")
        self.assertEqual(response.data["name"], "store/stones/test.jpg")
        self.assertEqual(response.data["url"], "https://example.com/signed/store/stones/test.jpg")
