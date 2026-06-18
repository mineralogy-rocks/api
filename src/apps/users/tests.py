# -*- coding: UTF-8 -*-
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from users.models import Space
from users.models import SpaceCollaborator
from users.models import User

# The test runner forces DEBUG=False, so urls.py never registers the 'djdt'
# namespace, yet the debug-toolbar middleware still runs and crashes on every
# response. Strip it for these tests.
_MIDDLEWARE_NO_DDT = [m for m in settings.MIDDLEWARE if "debug_toolbar" not in m]


@override_settings(MIDDLEWARE=_MIDDLEWARE_NO_DDT)
class AtomicCreateWithInviteesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@uni.edu", password="x")
        # Force JSON content negotiation so the Browsable API renderer (which
        # pulls in django-debug-toolbar under dev settings) is never used.
        self.client = APIClient(HTTP_ACCEPT="application/json")
        self.client.force_authenticate(user=self.owner)

    def _payload(self, invitees):
        return {
            "name": "My Space",
            "description": "desc",
            "access": 2,
            "invitees": invitees,
        }

    # Pass case 1: all-valid create-with-invitees commits atomically + emails attempted.
    @mock.patch("users.serializers.send_invitation_email")
    def test_all_valid_creates_space_and_invitations(self, mock_send):
        invitees = [
            {"email": "alice@uni.edu", "permission_level": 0},
            {"email": "bob@uni.edu", "permission_level": 1},
        ]
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post("/user/spaces/", self._payload(invitees), format="json")

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn("id", resp.data)
        space = Space.objects.get(id=resp.data["id"])

        for inv in invitees:
            collab = SpaceCollaborator.objects.get(space=space, invited_email=inv["email"])
            self.assertTrue(collab.is_pending)
            self.assertIsNone(collab.is_accepted)
            self.assertEqual(collab.permission_level, inv["permission_level"])
            self.assertTrue(collab.invitation_token)

        self.assertEqual(mock_send.call_count, len(invitees))

    # Pass case 2: a single malformed email rejects the whole request, no Space created.
    @mock.patch("users.serializers.send_invitation_email")
    def test_malformed_email_rejects_all(self, mock_send):
        invitees = [
            {"email": "alice@uni.edu", "permission_level": 0},
            {"email": "not-an-email", "permission_level": 0},
        ]
        resp = self.client.post("/user/spaces/", self._payload(invitees), format="json")

        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("invitees", resp.data)
        self.assertEqual(Space.objects.count(), 0)
        mock_send.assert_not_called()

    # Pass case 3a: owner's own email is rejected up-front, no Space created.
    @mock.patch("users.serializers.send_invitation_email")
    def test_owner_self_invite_rejected(self, mock_send):
        invitees = [{"email": "owner@uni.edu", "permission_level": 0}]
        resp = self.client.post("/user/spaces/", self._payload(invitees), format="json")

        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Space.objects.count(), 0)

    # Pass case 3b: intra-batch duplicate is rejected up-front, no Space created.
    @mock.patch("users.serializers.send_invitation_email")
    def test_duplicate_in_batch_rejected(self, mock_send):
        invitees = [
            {"email": "dup@uni.edu", "permission_level": 0},
            {"email": "dup@uni.edu", "permission_level": 1},
        ]
        resp = self.client.post("/user/spaces/", self._payload(invitees), format="json")

        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Space.objects.count(), 0)

    # Pass case 4: single-invite endpoint rewired onto shared service behaves identically.
    @mock.patch("users.views.send_invitation_email")
    def test_single_invite_endpoint_unchanged(self, mock_send):
        space = Space.objects.create(name="S", access=2, owner=self.owner)
        resp = self.client.post(
            f"/user/spaces/{space.id}/invite-collaborator/",
            {"email": "carol@uni.edu", "permission_level": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        collab = SpaceCollaborator.objects.get(space=space, invited_email="carol@uni.edu")
        self.assertTrue(collab.is_pending)
        self.assertIsNone(collab.is_accepted)
        self.assertEqual(collab.permission_level, 1)
        self.assertTrue(collab.invitation_token)
        mock_send.assert_called_once()

    # Inviting an existing user with a different-case email reuses that user (no duplicate).
    @mock.patch("users.views.send_invitation_email")
    def test_invite_matches_existing_user_case_insensitively(self, mock_send):
        existing = User.objects.create_user(email="erin@uni.edu", password="x")
        space = Space.objects.create(name="S", access=2, owner=self.owner)
        resp = self.client.post(
            f"/user/spaces/{space.id}/invite-collaborator/",
            {"email": "Erin@Uni.edu", "permission_level": 0},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        collab = SpaceCollaborator.objects.get(space=space)
        self.assertEqual(collab.user_id, existing.id)
        self.assertEqual(User.objects.filter(email__iexact="erin@uni.edu").count(), 1)

    # Pass case 5: email-send failure after commit does not roll back the Space.
    @mock.patch("users.serializers.send_invitation_email", side_effect=Exception("smtp down"))
    def test_email_failure_does_not_rollback(self, mock_send):
        invitees = [{"email": "dave@uni.edu", "permission_level": 0}]
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post("/user/spaces/", self._payload(invitees), format="json")

        self.assertEqual(resp.status_code, 201, resp.content)
        space = Space.objects.get(id=resp.data["id"])
        collab = SpaceCollaborator.objects.get(space=space, invited_email="dave@uni.edu")
        # Invitation persists and is resendable (still pending with a token).
        self.assertTrue(collab.is_pending)
        self.assertTrue(collab.invitation_token)
        self.assertTrue(mock_send.called)
