# -*- coding: UTF-8 -*-
import secrets
from datetime import timedelta

from core.utils import send_email
from django.conf import settings
from django.utils import timezone

from users.models import SpaceCollaborator


def generate_invitation_token():
    return secrets.token_urlsafe(48)


def send_invitation_email(email, space, inviter, token, permission_level_display, is_new_user=False):
    frontend_url = f"{settings.SCHEMA}://{settings.FRONTEND_DOMAIN}"
    accept_url = f"{frontend_url}/spaces/join?token={token}"
    decline_url = f"{frontend_url}/invitations/decline?token={token}"

    inviter_name = inviter.get_full_name() or inviter.username or inviter.email

    context = {
        "inviter_name": inviter_name,
        "inviter_email": inviter.email,
        "space_name": space.name,
        "space_description": space.description,
        "permission_level": permission_level_display,
        "accept_url": accept_url,
        "decline_url": decline_url,
        "is_new_user": is_new_user,
    }

    subject = f"Invitation to collaborate on {space.name} - mineralogy.rocks"
    template = "invitation_email.html"

    send_email(subject, template, [email], context)


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
