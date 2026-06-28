import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from store.models import Stone
from store.models import StoneColor
from store.models import StoneCut
from store.models import StoneImage
from store.models import StoneTreatment
from users.models import User


def _make_user(email, is_staff):
    user = User.objects.create_user(email=email, password="pass123")
    user.is_active = True
    user.is_staff = is_staff
    user.save()
    return user


class StoneApiBaseTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = _make_user("staff-stone@example.com", is_staff=True)
        cls.regular = _make_user("regular-stone@example.com", is_staff=False)

        cls.color_red = StoneColor.objects.create(name="Red", hex="#ff0000")
        cls.color_blue = StoneColor.objects.create(name="Blue", hex="#0000ff")
        cls.cut_oval = StoneCut.objects.create(name="Oval")
        cls.cut_round = StoneCut.objects.create(name="Round")
        cls.treatment_none = StoneTreatment.objects.create(name="Untreated")
        cls.treatment_heat = StoneTreatment.objects.create(name="Heated")

    def _create_stone(self, name="Stone", created_at=None, **kwargs):
        params = {
            "name": name,
            "is_selling": True,
            "is_sold": False,
        }
        params.update(kwargs)
        stone = Stone.objects.create(**params)
        if created_at is not None:
            Stone.objects.filter(pk=stone.pk).update(created_at=created_at)
            stone.refresh_from_db()
        return stone


class AdminCrudGatingTest(StoneApiBaseTest):
    def test_staff_can_create_update_delete_stone(self):
        self.client.force_login(self.staff)

        payload = {
            "name": "Admin Ruby",
            "color_id": self.color_red.id,
            "cut_id": self.cut_oval.id,
            "treatment_id": self.treatment_heat.id,
            "selling_price": "150.00",
            "price_usd": "100.00",
            "shipment_usd": "10.00",
            "vat_usd": "5.00",
            "is_selling": True,
            "images": [
                {"image_url": "second.jpg", "display_order": 1},
                {"image_url": "first.jpg", "display_order": 0},
            ],
        }
        response = self.client.post("/store/stones/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stone_id = response.data["id"]
        self.assertEqual(response.data["gross_usd"], "115.00")
        self.assertEqual(StoneImage.objects.filter(stone_id=stone_id).count(), 2)

        patch = self.client.patch(
            f"/store/stones/{stone_id}/",
            {"selling_price": "175.00"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data["selling_price"], "175.00")

        delete = self.client.delete(f"/store/stones/{stone_id}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Stone.objects.filter(pk=stone_id).exists())

    def test_staff_can_crud_lookups(self):
        self.client.force_login(self.staff)
        for endpoint, body in (
            ("/store/stone-colors/", {"name": "Teal", "hex": "#00ced1"}),
            ("/store/stone-cuts/", {"name": "Emerald"}),
            ("/store/stone-treatments/", {"name": "Irradiated"}),
        ):
            created = self.client.post(endpoint, body, format="json")
            self.assertEqual(created.status_code, status.HTTP_201_CREATED, endpoint)
            self.assertTrue(created.data["slug"])
            obj_id = created.data["id"]

            patched = self.client.patch(f"{endpoint}{obj_id}/", {"name": body["name"] + " X"}, format="json")
            self.assertEqual(patched.status_code, status.HTTP_200_OK, endpoint)

            removed = self.client.delete(f"{endpoint}{obj_id}/")
            self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT, endpoint)

    def test_anonymous_write_is_rejected(self):
        response = self.client.post("/store/stones/", {"name": "Nope"}, format="json")
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

        color = self.client.post("/store/stone-colors/", {"name": "Nope"}, format="json")
        self.assertIn(color.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_non_staff_write_is_forbidden(self):
        self.client.force_login(self.regular)
        stone = self._create_stone(name="Existing", selling_price="10.00")

        create = self.client.post("/store/stones/", {"name": "Nope"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

        patch = self.client.patch(f"/store/stones/{stone.id}/", {"name": "Hacked"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

        delete = self.client.delete(f"/store/stones/{stone.id}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)


class PublicReadFilteringTest(StoneApiBaseTest):
    def setUp(self):
        self.visible_a = self._create_stone(name="Visible A", selling_price="100.00")
        self.visible_b = self._create_stone(name="Visible B", selling_price="200.00")
        self.sold = self._create_stone(name="Sold", is_sold=True, is_selling=True, selling_price="50.00")
        self.not_selling = self._create_stone(name="Draft", is_selling=False, selling_price="70.00")

    def test_anonymous_list_shows_all_selling_including_sold(self):
        response = self.client.get("/store/stones/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {str(self.visible_a.id), str(self.visible_b.id), str(self.sold.id)})
        self.assertNotIn(str(self.not_selling.id), ids)

    def test_anonymous_can_filter_available_only(self):
        response = self.client.get("/store/stones/?is_sold=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {str(self.visible_a.id), str(self.visible_b.id)})
        self.assertNotIn(str(self.sold.id), ids)

    def test_staff_list_sees_everything(self):
        self.client.force_login(self.staff)
        response = self.client.get("/store/stones/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)


class FilterSortTest(StoneApiBaseTest):
    def setUp(self):
        base = timezone.now()
        self.cheap = self._create_stone(
            name="Cheap",
            selling_price="10.00",
            weight_carats="1.000",
            color=self.color_red,
            cut=self.cut_oval,
            created_at=base - datetime.timedelta(minutes=3),
        )
        self.mid = self._create_stone(
            name="Mid",
            selling_price="20.00",
            weight_carats="2.000",
            color=self.color_blue,
            cut=self.cut_round,
            created_at=base - datetime.timedelta(minutes=2),
        )
        self.pricey = self._create_stone(
            name="Pricey",
            selling_price="30.00",
            weight_carats="3.000",
            color=self.color_red,
            cut=self.cut_round,
            created_at=base - datetime.timedelta(minutes=1),
        )

    def _ids(self, response):
        return [row["id"] for row in response.data["results"]]

    def test_price_range(self):
        response = self.client.get("/store/stones/", {"min_price": "15", "max_price": "25"})
        self.assertEqual(self._ids(response), [str(self.mid.id)])

    def test_weight_range(self):
        response = self.client.get("/store/stones/", {"min_weight": "2.5"})
        self.assertEqual(self._ids(response), [str(self.pricey.id)])

    def test_color_filter_in(self):
        response = self.client.get("/store/stones/", {"color": f"{self.color_red.id}"})
        self.assertEqual(set(self._ids(response)), {str(self.cheap.id), str(self.pricey.id)})

    def test_cut_filter(self):
        response = self.client.get("/store/stones/", {"cut": f"{self.cut_round.id}"})
        self.assertEqual(set(self._ids(response)), {str(self.mid.id), str(self.pricey.id)})

    def test_ordering_selling_price(self):
        asc = self.client.get("/store/stones/", {"ordering": "selling_price"})
        self.assertEqual(self._ids(asc), [str(self.cheap.id), str(self.mid.id), str(self.pricey.id)])

        desc = self.client.get("/store/stones/", {"ordering": "-selling_price"})
        self.assertEqual(self._ids(desc), [str(self.pricey.id), str(self.mid.id), str(self.cheap.id)])

    def test_default_ordering_newest_first(self):
        response = self.client.get("/store/stones/")
        self.assertEqual(self._ids(response), [str(self.pricey.id), str(self.mid.id), str(self.cheap.id)])


class PaginationTest(StoneApiBaseTest):
    def setUp(self):
        base = timezone.now()
        self.stones = [
            self._create_stone(
                name=f"S{index}",
                selling_price=f"{index}.00",
                created_at=base - datetime.timedelta(minutes=index),
            )
            for index in range(12)
        ]

    def test_limit_offset_paging(self):
        first = self.client.get("/store/stones/", {"limit": "5", "ordering": "selling_price"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 5)
        self.assertIsNotNone(first.data["next"])

        last = self.client.get("/store/stones/", {"limit": "5", "offset": "10", "ordering": "selling_price"})
        self.assertEqual(len(last.data["results"]), 2)
        self.assertIsNone(last.data["next"])


class SearchTest(StoneApiBaseTest):
    def setUp(self):
        self.ruby = self._create_stone(name="Burmese Ruby", mineral="Corundum", country="Myanmar", selling_price="9")
        self.opal = self._create_stone(name="Fire Opal", mineral="Opal", country="Australia", selling_price="9")

    def test_search_matches_name(self):
        response = self.client.get("/store/stones/", {"q": "Ruby"})
        self.assertEqual([row["id"] for row in response.data["results"]], [str(self.ruby.id)])

    def test_search_matches_country(self):
        response = self.client.get("/store/stones/", {"q": "Australia"})
        self.assertEqual([row["id"] for row in response.data["results"]], [str(self.opal.id)])

    def test_search_matches_mineral(self):
        response = self.client.get("/store/stones/", {"q": "Corundum"})
        self.assertEqual([row["id"] for row in response.data["results"]], [str(self.ruby.id)])


class DetailTest(StoneApiBaseTest):
    def setUp(self):
        self.stone = self._create_stone(name="Detailed", selling_price="42.00")
        StoneImage.objects.create(stone=self.stone, image_url="b.jpg", display_order=2)
        StoneImage.objects.create(stone=self.stone, image_url="a.jpg", display_order=1)
        self.sold = self._create_stone(name="Gone", is_sold=True, selling_price="42.00")
        self.not_selling = self._create_stone(name="Draft", is_selling=False, selling_price="42.00")

    def test_anonymous_detail_images_ordered_and_has_report(self):
        response = self.client.get(f"/store/stones/{self.stone.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["has_report"], False)

        images = response.data["images"]
        self.assertEqual([img["display_order"] for img in images], [1, 2])
        self.assertEqual(images[0]["image_url"], "https://s3.local/mr-dev/gems/a.jpg")
        self.assertIn("gems/", images[1]["image_url"])

    def test_sold_selling_detail_visible_to_anon(self):
        response = self.client.get(f"/store/stones/{self.sold.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_not_selling_detail_hidden_from_anon_visible_to_staff(self):
        anon = self.client.get(f"/store/stones/{self.not_selling.id}/")
        self.assertEqual(anon.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.staff)
        staff = self.client.get(f"/store/stones/{self.not_selling.id}/")
        self.assertEqual(staff.status_code, status.HTTP_200_OK)


class BulkDeleteTest(StoneApiBaseTest):
    def setUp(self):
        self.a = self._create_stone(name="A", selling_price="1")
        self.b = self._create_stone(name="B", selling_price="2")
        self.c = self._create_stone(name="C", selling_price="3")

    def test_staff_bulk_delete(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/store/stones/bulk-delete/",
            {"ids": [str(self.a.id), str(self.b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 2)
        self.assertFalse(Stone.objects.filter(pk__in=[self.a.id, self.b.id]).exists())
        self.assertTrue(Stone.objects.filter(pk=self.c.id).exists())

    def test_bulk_delete_rejects_empty(self):
        self.client.force_login(self.staff)
        response = self.client.post("/store/stones/bulk-delete/", {"ids": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_staff_bulk_delete_forbidden(self):
        self.client.force_login(self.regular)
        response = self.client.post(
            "/store/stones/bulk-delete/",
            {"ids": [str(self.a.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Stone.objects.filter(pk=self.a.id).exists())


class CostFieldPrivacyTest(StoneApiBaseTest):
    def setUp(self):
        self.stone = self._create_stone(
            name="Priced",
            selling_price="100.00",
            price_eur="80.00",
            price_usd="90.00",
            vat_eur="5.00",
        )

    def test_anonymous_response_hides_cost_fields(self):
        listing = self.client.get("/store/stones/")
        row = listing.data["results"][0]
        for field in ("price_eur", "price_usd", "gross_eur", "gross_usd", "vat_eur", "notes"):
            self.assertNotIn(field, row)

        detail = self.client.get(f"/store/stones/{self.stone.id}/")
        for field in ("price_eur", "gross_eur"):
            self.assertNotIn(field, detail.data)

    def test_staff_response_includes_cost_fields(self):
        self.client.force_login(self.staff)
        listing = self.client.get("/store/stones/")
        row = listing.data["results"][0]
        for field in ("price_eur", "price_usd", "gross_eur", "gross_usd"):
            self.assertIn(field, row)


class FacetsTest(StoneApiBaseTest):
    def setUp(self):
        self._create_stone(
            name="Facet A",
            selling_price="10.00",
            weight_carats="1.500",
            color=self.color_red,
            cut=self.cut_oval,
        )
        self._create_stone(
            name="Facet B",
            selling_price="50.00",
            weight_carats="4.000",
            color=self.color_blue,
            cut=self.cut_round,
        )
        self._create_stone(name="Sold Selling", is_sold=True, selling_price="999.00", color=self.color_red)
        self._create_stone(name="Not Selling", is_selling=False, selling_price="5.00", color=self.color_blue)

    def test_facets_for_anonymous(self):
        response = self.client.get("/store/stones/facets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["priceRange"], {"min": 10.0, "max": 999.0})
        self.assertEqual(response.data["weightRange"], {"min": 1.5, "max": 4.0})
        self.assertEqual({c["id"] for c in response.data["colors"]}, {self.color_red.id, self.color_blue.id})
        self.assertEqual([c["name"] for c in response.data["cuts"]], ["Oval", "Round"])
