from urllib.parse import urlencode
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseBadRequest
from social_core.exceptions import AuthForbidden
from users.tokens import OneTimeToken


def require_allowlisted_email(backend, details, *args, **kwargs):
    email = (details.get("email") or "").strip().lower()
    if not email or email not in settings.AUTH_EMAIL_ALLOWLIST:
        raise AuthForbidden(backend, "email_not_allowlisted")


def grant_staff(backend, user, *args, **kwargs):
    if user is None:
        return
    updated = False
    if not user.is_staff:
        user.is_staff = True
        updated = True
    if not user.is_active:
        user.is_active = True
        updated = True
    if updated:
        user.save(update_fields=["is_staff", "is_active"])


def resolve_frontend_callback_url(strategy):
    requested = strategy.session_get("next") or ""
    if requested and urlparse(requested).netloc in settings.SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS:
        return requested
    return None


def frontend_error_url(strategy, code="auth"):
    callback_url = resolve_frontend_callback_url(strategy)
    if not callback_url:
        return None
    return f"{callback_url}?{urlencode({'error': code})}"


def issue_token_and_redirect(strategy, user, *args, **kwargs):
    callback_url = resolve_frontend_callback_url(strategy)
    if not callback_url:
        return HttpResponseBadRequest("Missing or untrusted redirect target")
    token = str(OneTimeToken.for_user(user))
    url = f"{callback_url}?{urlencode({'token': token})}"
    return strategy.redirect(url)
