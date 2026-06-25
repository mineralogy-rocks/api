from unittest.mock import MagicMock

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from social_core.exceptions import AuthForbidden

from users.models import User
from users.pipeline import grant_staff
from users.pipeline import require_allowlisted_email
from users.tokens import OneTimeToken


class RequireAllowlistedEmailTests(APITestCase):
    def test_raises_for_non_allowlisted_email(self):
        backend = MagicMock()
        with override_settings(AUTH_EMAIL_ALLOWLIST=["allowed@example.com"]):
            with self.assertRaises(AuthForbidden):
                require_allowlisted_email(backend=backend, details={"email": "other@example.com"})

    def test_passes_for_allowlisted_email(self):
        backend = MagicMock()
        with override_settings(AUTH_EMAIL_ALLOWLIST=["allowed@example.com"]):
            result = require_allowlisted_email(backend=backend, details={"email": "allowed@example.com"})
            self.assertIsNone(result)

    def test_raises_for_empty_email(self):
        backend = MagicMock()
        with override_settings(AUTH_EMAIL_ALLOWLIST=["allowed@example.com"]):
            with self.assertRaises(AuthForbidden):
                require_allowlisted_email(backend=backend, details={"email": ""})


class GrantStaffTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com", password="testpass123")
        self.user.is_staff = False
        self.user.is_active = False
        self.user.save()

    def test_sets_is_staff_and_is_active(self):
        backend = MagicMock()
        grant_staff(backend=backend, user=self.user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.is_active)

    def test_noop_when_user_is_none(self):
        backend = MagicMock()
        result = grant_staff(backend=backend, user=None)
        self.assertIsNone(result)


class SessionExchangeViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="active@example.com", password="testpass123")
        self.user.is_active = True
        self.user.save()
        self.url = "/auth/session/"

    def test_valid_ott_establishes_session(self):
        token = str(OneTimeToken.for_user(self.user))
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sessionid", response.cookies)
        self.assertEqual(response.data["email"], self.user.email)

    def test_second_use_returns_400(self):
        token = str(OneTimeToken.for_user(self.user))
        self.client.post(self.url, {"token": token}, format="json")
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_garbage_token_returns_400(self):
        response = self.client.post(self.url, {"token": "not-a-real-token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
