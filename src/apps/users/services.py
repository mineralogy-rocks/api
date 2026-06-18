# -*- coding: UTF-8 -*-
import secrets
from datetime import timedelta

from core.utils import send_email
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from users.models import PasswordResetToken
from users.models import SpaceCollaborator
from users.models import User


def generate_invitation_token():
    return secrets.token_urlsafe(48)


def send_invitation_email(email, space, inviter, token, permission_level_display, is_new_user=False):
    frontend_url = f"{settings.SCHEMA}://{settings.FRONTEND_DOMAIN}"
    accept_url = f"{frontend_url}/hub/spaces/join?token={token}"

    inviter_name = inviter.get_full_name() or inviter.username or inviter.email

    context = {
        "inviter_name": inviter_name,
        "inviter_email": inviter.email,
        "space_name": space.name,
        "space_description": space.description,
        "permission_level": permission_level_display,
        "accept_url": accept_url,
        "is_new_user": is_new_user,
    }

    subject = f"Invitation to collaborate on {space.name} - mineralogy.rocks"
    template = "invitation_email.html"

    send_email(subject, template, [email], context)


def invite_user_to_space(space, email, permission_level, invited_by):
    try:
        # Case-insensitive: the serializer normalizes invitee emails to lowercase,
        # and only the email domain is normalized on user creation, so an exact
        # match could miss an existing user and mint a near-duplicate account.
        user = User.objects.get(email__iexact=email)
        is_new_user = False
    except User.DoesNotExist:
        user = User.objects.create_user(email=email, password=None, is_active=False)
        is_new_user = True

    existing = SpaceCollaborator.objects.filter(space=space, user=user).first()

    if existing and existing.is_accepted:
        raise ValidationError("User is already a collaborator")

    token = generate_invitation_token()
    invitation_sent_at = timezone.now()
    invitation_expires_at = calculate_expiration_date(days=7)

    if existing and existing.is_pending:
        existing.invitation_token = token
        existing.invitation_sent_at = invitation_sent_at
        existing.invitation_expires_at = invitation_expires_at
        existing.permission_level = permission_level
        existing.invited_by = invited_by
        existing.invited_email = email
        existing.save()
        collaboration = existing
    else:
        collaboration = SpaceCollaborator.objects.create(
            space=space,
            user=user,
            permission_level=permission_level,
            is_pending=True,
            is_accepted=None,
            invitation_token=token,
            invitation_sent_at=invitation_sent_at,
            invitation_expires_at=invitation_expires_at,
            invited_email=email,
            invited_by=invited_by,
        )

    return (collaboration, is_new_user)


def validate_invitation_token(token):
    try:
        invitation = SpaceCollaborator.objects.get(
            invitation_token=token,
            is_pending=True,
        )

        if invitation.is_revoked:
            return None, "Invitation has been revoked"

        if invitation.invitation_expires_at and invitation.invitation_expires_at < timezone.now():
            return None, "Invitation has expired"

        return invitation, None

    except SpaceCollaborator.DoesNotExist:
        return None, "Invalid invitation token"


def calculate_expiration_date(days=7):
    return timezone.now() + timedelta(days=days)


def generate_password_reset_token(user):
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

    token = secrets.token_urlsafe(48)
    expires_at = calculate_expiration_date(days=1)

    password_reset_token = PasswordResetToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at,
    )

    return password_reset_token


def validate_password_reset_token(token):
    try:
        token_obj = PasswordResetToken.objects.get(token=token)

        if token_obj.is_used:
            return None, "This password reset link has already been used"

        if token_obj.expires_at < timezone.now():
            return None, "This password reset link has expired"

        return token_obj, None

    except PasswordResetToken.DoesNotExist:
        return None, "Invalid password reset token"


def send_password_reset_email(user, token):
    frontend_url = f"{settings.SCHEMA}://{settings.FRONTEND_DOMAIN}"
    reset_url = f"{frontend_url}/auth/reset-password?token={token}"

    context = {
        "user_email": user.email,
        "reset_url": reset_url,
    }

    subject = "Reset your password - mineralogy.rocks"
    template = "password_reset_email.html"

    send_email(subject, template, [user.email], context)
