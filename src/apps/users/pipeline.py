from urllib.parse import urlencode

from django.conf import settings
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


def issue_token_and_redirect(strategy, user, *args, **kwargs):
    token = str(OneTimeToken.for_user(user))
    url = f"{settings.AUTH_FRONTEND_CALLBACK_URL}?{urlencode({'token': token})}"
    return strategy.redirect(url)
