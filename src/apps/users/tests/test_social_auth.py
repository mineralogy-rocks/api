from unittest.mock import MagicMock

from django.http import HttpResponseBadRequest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from social_core.exceptions import AuthForbidden
from users.middleware import FrontendRedirectExceptionMiddleware
from users.models import User
from users.pipeline import frontend_error_url
from users.pipeline import grant_staff
from users.pipeline import issue_token_and_redirect
from users.pipeline import require_allowlisted_email
from users.pipeline import resolve_frontend_callback_url
from users.tokens import OneTimeToken


def _strategy(next_value):
    strategy = MagicMock()
    strategy.session_get.return_value = next_value
    return strategy


class ResolveFrontendCallbackUrlTests(APITestCase):
    settings_kwargs = {
        "SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS": ["gemsla.be.local", "mineralogy.rocks.local"],
    }

    def test_returns_requested_next_when_host_allowed(self):
        with override_settings(**self.settings_kwargs):
            url = resolve_frontend_callback_url(_strategy("http://mineralogy.rocks.local/auth/callback"))
            self.assertEqual(url, "http://mineralogy.rocks.local/auth/callback")

    def test_returns_none_when_host_not_allowed(self):
        with override_settings(**self.settings_kwargs):
            self.assertIsNone(resolve_frontend_callback_url(_strategy("http://evil.example.com/auth/callback")))

    def test_returns_none_when_next_missing(self):
        with override_settings(**self.settings_kwargs):
            self.assertIsNone(resolve_frontend_callback_url(_strategy("")))


class IssueTokenAndRedirectTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="active@example.com", password="testpass123")
        self.user.is_active = True
        self.user.save()

    @override_settings(SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["mineralogy.rocks.local"])
    def test_redirects_to_requested_frontend_with_token(self):
        strategy = _strategy("http://mineralogy.rocks.local/auth/callback")
        issue_token_and_redirect(strategy, self.user)
        redirected_to = strategy.redirect.call_args[0][0]
        self.assertTrue(redirected_to.startswith("http://mineralogy.rocks.local/auth/callback?token="))

    @override_settings(SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["mineralogy.rocks.local"])
    def test_returns_bad_request_without_token_when_next_untrusted(self):
        strategy = _strategy("http://evil.example.com/auth/callback")
        response = issue_token_and_redirect(strategy, self.user)
        self.assertIsInstance(response, HttpResponseBadRequest)
        strategy.redirect.assert_not_called()


class FrontendErrorRoutingTests(APITestCase):
    settings_kwargs = {"SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS": ["mineralogy.rocks.local"]}

    def test_error_url_points_to_requesting_frontend(self):
        with override_settings(**self.settings_kwargs):
            url = frontend_error_url(_strategy("http://mineralogy.rocks.local/auth/callback"))
            self.assertEqual(url, "http://mineralogy.rocks.local/auth/callback?error=auth")

    def test_error_url_none_when_next_untrusted(self):
        with override_settings(**self.settings_kwargs):
            self.assertIsNone(frontend_error_url(_strategy("http://evil.example.com/auth/callback")))

    def test_middleware_redirects_errors_to_requesting_frontend(self):
        with override_settings(**self.settings_kwargs):
            request = MagicMock()
            request.social_strategy = _strategy("http://mineralogy.rocks.local/auth/callback")
            middleware = FrontendRedirectExceptionMiddleware(lambda r: None)
            url = middleware.get_redirect_uri(request, AuthForbidden(MagicMock()))
            self.assertEqual(url, "http://mineralogy.rocks.local/auth/callback?error=auth")


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
