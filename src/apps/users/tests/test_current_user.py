from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class CurrentUserPermissionTests(APITestCase):
    def setUp(self):
        self.url = "/user/me/"
        self.user = User.objects.create_user(email="authed@example.com", password="pass123")
        self.user.is_active = True
        self.user.is_staff = False
        self.user.save()

    def test_anonymous_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_returns_200_with_is_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("is_staff", response.data)
