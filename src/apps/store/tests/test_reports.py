from rest_framework import status
from rest_framework.test import APITestCase
from store.models import Report
from store.models import ReportImage
from store.models import Stone
from users.models import User


def _make_user(email, is_staff):
    user = User.objects.create_user(email=email, password="pass123")
    user.is_active = True
    user.is_staff = is_staff
    user.save()
    return user


class ReportApiBaseTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = _make_user("staff-report@example.com", is_staff=True)
        cls.regular = _make_user("regular-report@example.com", is_staff=False)
        cls.customer = _make_user("customer-report@example.com", is_staff=False)

    def _create_report(self, title="Report", public=False, **kwargs):
        params = {"title": title, "public": public}
        params.update(kwargs)
        return Report.objects.create(**params)


class AdminCrudGatingTest(ReportApiBaseTest):
    def test_staff_can_create_update_delete_report(self):
        self.client.force_login(self.staff)

        payload = {
            "title": "Emerald cert",
            "stone": "Emerald",
            "description": "A fine emerald",
            "note": "internal note",
            "first_name": "Jane",
            "last_name": "Doe",
            "owner_email": "jane@example.com",
            "carat_weight": "2.500",
            "refractive_index": "1.577",
            "origin": "Colombia",
            "currency": "USD",
            "price": "1000.00",
            "public": False,
            "report_images": [
                {"image_url": "store/reports/img-1.jpg", "title": "Front", "is_headline": True},
                {"image_url": "store/reports/img-2.jpg", "display_order": 1},
            ],
        }
        create = self.client.post("/store/reports/", payload, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.content)
        report_id = create.data["id"]
        self.assertEqual(Report.objects.get(pk=report_id).images.count(), 2)

        update = self.client.patch(f"/store/reports/{report_id}/", {"title": "Emerald cert v2"}, format="json")
        self.assertEqual(update.status_code, status.HTTP_200_OK, update.content)
        self.assertEqual(Report.objects.get(pk=report_id).title, "Emerald cert v2")

        delete = self.client.delete(f"/store/reports/{report_id}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Report.objects.filter(pk=report_id).exists())

    def test_owner_resolved_from_email(self):
        self.client.force_login(self.staff)
        payload = {"title": "Owned", "owner_email": self.customer.email}
        create = self.client.post("/store/reports/", payload, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.content)
        report = Report.objects.get(pk=create.data["id"])
        self.assertEqual(report.owner_id, self.customer.id)

    def test_anonymous_cannot_write(self):
        report = self._create_report(public=True)
        rejected = (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        self.assertIn(self.client.post("/store/reports/", {"title": "x"}, format="json").status_code, rejected)
        self.assertIn(
            self.client.patch(f"/store/reports/{report.id}/", {"title": "x"}, format="json").status_code,
            rejected,
        )
        self.assertIn(self.client.delete(f"/store/reports/{report.id}/").status_code, rejected)

    def test_non_staff_cannot_write(self):
        self.client.force_login(self.regular)
        report = self._create_report(public=True)
        self.assertEqual(
            self.client.post("/store/reports/", {"title": "x"}, format="json").status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.patch(f"/store/reports/{report.id}/", {"title": "x"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )


class PublicVisibilityTest(ReportApiBaseTest):
    def test_anonymous_only_sees_public_reports(self):
        public = self._create_report(title="Public", public=True)
        self._create_report(title="Private", public=False)

        response = self.client.get("/store/reports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public.id))

    def test_anonymous_cannot_read_private_report(self):
        private = self._create_report(public=False)
        response = self.client.get(f"/store/reports/{private.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_can_read_public_report(self):
        public = self._create_report(public=True)
        response = self.client.get(f"/store/reports/{public.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(public.id))

    def test_staff_sees_all_reports(self):
        self.client.force_login(self.staff)
        self._create_report(title="Public", public=True)
        self._create_report(title="Private", public=False)
        response = self.client.get("/store/reports/")
        self.assertEqual(response.data["count"], 2)

    def test_toggle_public_exposes_share_link(self):
        report = self._create_report(public=False)
        self.assertEqual(self.client.get(f"/store/reports/{report.id}/").status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.staff)
        toggled = self.client.patch(f"/store/reports/{report.id}/toggle-public/", {}, format="json")
        self.assertEqual(toggled.status_code, status.HTTP_200_OK, toggled.content)
        self.assertTrue(toggled.data["public"])

        self.client.logout()
        self.assertEqual(self.client.get(f"/store/reports/{report.id}/").status_code, status.HTTP_200_OK)

        self.client.force_login(self.staff)
        self.client.patch(f"/store/reports/{report.id}/toggle-public/", {}, format="json")
        self.client.logout()
        self.assertEqual(self.client.get(f"/store/reports/{report.id}/").status_code, status.HTTP_404_NOT_FOUND)


class AdminFieldStrippingTest(ReportApiBaseTest):
    def test_public_serializer_hides_admin_only_fields(self):
        report = self._create_report(public=True, note="secret", owner_telephone="+100", currency="USD", price="50.00")
        response = self.client.get(f"/store/reports/{report.id}/")
        for field in ("note", "owner_telephone", "currency", "price"):
            self.assertNotIn(field, response.data)

    def test_admin_serializer_includes_admin_only_fields(self):
        self.client.force_login(self.staff)
        report = self._create_report(public=True, note="secret", currency="USD", price="50.00")
        response = self.client.get(f"/store/reports/{report.id}/")
        for field in ("note", "owner_telephone", "currency", "price"):
            self.assertIn(field, response.data)


class SignedUrlTest(ReportApiBaseTest):
    def test_public_report_images_expose_signed_url(self):
        report = self._create_report(public=True)
        ReportImage.objects.create(report=report, image_url="store/reports/secret.jpg", display_order=0)
        response = self.client.get(f"/store/reports/{report.id}/")
        images = response.data["report_images"]
        self.assertEqual(len(images), 1)
        self.assertIn("signed_url", images[0])
        signed = images[0]["signed_url"]
        self.assertTrue(signed)
        self.assertIn("?", signed)
        self.assertTrue(
            any(marker in signed for marker in ("X-Amz-", "Signature", "Expires")),
            msg=f"expected an expiring signed URL, got {signed}",
        )


class SearchTest(ReportApiBaseTest):
    def test_search_matches_title_customer_email_stone(self):
        self.client.force_login(self.staff)
        self._create_report(
            title="Ruby Star", stone="Ruby", first_name="Alice", last_name="Smith", owner_email="alice@example.com"
        )
        self._create_report(
            title="Blue Topaz", stone="Topaz", first_name="Bob", last_name="Jones", owner_email="bob@example.com"
        )

        self.assertEqual(self.client.get("/store/reports/?q=Ruby Star").data["count"], 1)
        self.assertEqual(self.client.get("/store/reports/?q=Alice").data["count"], 1)
        self.assertEqual(self.client.get("/store/reports/?q=bob@example.com").data["count"], 1)
        self.assertEqual(self.client.get("/store/reports/?q=Topaz").data["count"], 1)

    def test_search_unlinked_endpoint(self):
        self.client.force_login(self.staff)
        self._create_report(title="Unlinked Garnet", stone="Garnet")
        response = self.client.get("/store/reports/search/?q=Garnet")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)


class StoneLinkingTest(ReportApiBaseTest):
    def test_link_report_to_stone(self):
        self.client.force_login(self.staff)
        stone = Stone.objects.create(name="Inventory Ruby", is_selling=True)
        report = self._create_report(title="Linkable")

        response = self.client.patch(f"/store/reports/{report.id}/", {"stone_id": str(stone.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(str(response.data["stone_id"]), str(stone.id))
        self.assertEqual(str(response.data["linked_stone"]["id"]), str(stone.id))

        report.refresh_from_db()
        self.assertEqual(report.linked_stone_id, stone.id)
        self.assertTrue(stone.has_report)

    def test_cannot_link_already_linked_stone(self):
        self.client.force_login(self.staff)
        stone = Stone.objects.create(name="Shared", is_selling=True)
        first = self._create_report(title="First", linked_stone=stone)
        second = self._create_report(title="Second")

        response = self.client.patch(f"/store/reports/{second.id}/", {"stone_id": str(stone.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotEqual(first.linked_stone_id, None)


class ExportTest(ReportApiBaseTest):
    def test_pdf_export_for_public_report(self):
        report = self._create_report(title="Exportable", stone="Sapphire", public=True, refractive_index="1.76")
        response = self.client.get(f"/store/reports/{report.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_export_private_report_blocked_for_anonymous(self):
        report = self._create_report(title="Private export", public=False)
        response = self.client.get(f"/store/reports/{report.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_qr_sheet_export(self):
        self.client.force_login(self.staff)
        self._create_report(title="QR me", stone="Diamond", public=True)
        response = self.client.get("/store/reports/export-qr/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_qr_sheet_export_requires_staff(self):
        response = self.client.get("/store/reports/export-qr/")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
