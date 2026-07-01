from blog.models import Channel
from blog.models import Post
from blog.models import Tag
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User

CONTENT_JSON = {"type": "doc", "content": [{"type": "paragraph"}]}


def _make_user(email, is_staff):
    user = User.objects.create_user(email=email, password="pass123")
    user.is_active = True
    user.is_staff = is_staff
    user.save()
    return user


class BlogApiBaseTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = _make_user("staff-blog@example.com", is_staff=True)
        cls.regular = _make_user("regular-blog@example.com", is_staff=False)

        cls.channel_mr, _ = Channel.objects.get_or_create(
            host="mineralogy.rocks", defaults={"name": "mineralogy.rocks"}
        )
        cls.channel_gem, _ = Channel.objects.get_or_create(host="gemsla.be", defaults={"name": "gemsla.be"})

    def _create_post(self, name, slug, channels=(), is_published=True, **kwargs):
        params = {
            "name": name,
            "slug": slug,
            "description": "desc",
            "is_published": is_published,
        }
        if is_published and "published_at" not in kwargs:
            params["published_at"] = timezone.now()
        params.update(kwargs)
        post = Post.objects.create(**params)
        if channels:
            post.channels.set(channels)
        return post


class AdminCrudGatingTest(BlogApiBaseTest):
    def test_anonymous_write_is_rejected(self):
        post = self._create_post("Anon Target", "anon-target", channels=[self.channel_mr])

        create = self.client.post("/blog/post/", {"name": "Nope", "slug": "nope"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

        patch = self.client.patch(f"/blog/post/{post.slug}/", {"description": "Hacked"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

        delete = self.client.delete(f"/blog/post/{post.slug}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_write_is_forbidden(self):
        self.client.force_login(self.regular)
        post = self._create_post("Reg Target", "reg-target", channels=[self.channel_mr])

        create = self.client.post("/blog/post/", {"name": "Nope", "slug": "nope"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

        patch = self.client.patch(f"/blog/post/{post.slug}/", {"description": "Hacked"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

        delete = self.client.delete(f"/blog/post/{post.slug}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_update_delete(self):
        self.client.force_login(self.staff)

        payload = {
            "name": "Gem Post",
            "slug": "gem-post",
            "description": "A gem story",
            "content": "",
            "content_json": CONTENT_JSON,
            "channel_hosts": ["gemsla.be"],
            "tag_names": ["Sapphire"],
            "is_published": True,
            "published_at": "2026-06-29T00:00:00Z",
        }
        create = self.client.post("/blog/post/", payload, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create.data["content_json"], CONTENT_JSON)
        self.assertEqual({c["host"] for c in create.data["channels"]}, {"gemsla.be"})
        self.assertEqual({t["name"] for t in create.data["tags"]}, {"Sapphire"})

        self.assertTrue(Tag.objects.filter(name="Sapphire").exists())
        post = Post.objects.get(slug="gem-post")
        self.assertEqual(set(post.channels.values_list("host", flat=True)), {"gemsla.be"})

        patch = self.client.patch(
            "/blog/post/gem-post/",
            {"description": "Updated story"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data["description"], "Updated story")

        delete = self.client.delete("/blog/post/gem-post/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(slug="gem-post").exists())

    def test_staff_mutates_non_default_channel_post_without_host_param(self):
        self.client.force_login(self.staff)
        post = self._create_post("Gem Edit", "gem-edit", channels=[self.channel_gem])

        patch = self.client.patch(f"/blog/post/{post.slug}/", {"description": "Edited"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data["description"], "Edited")

        delete = self.client.delete(f"/blog/post/{post.slug}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(slug="gem-edit").exists())


class ChannelAssignmentTest(BlogApiBaseTest):
    def test_staff_replaces_channel_assignment(self):
        self.client.force_login(self.staff)
        post = self._create_post("Chan Post", "chan-post", channels=[self.channel_mr])

        first = self.client.patch(
            f"/blog/post/{post.slug}/",
            {"channel_hosts": ["gemsla.be"]},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(set(post.channels.values_list("host", flat=True)), {"gemsla.be"})

        second = self.client.patch(
            f"/blog/post/{post.slug}/",
            {"channel_hosts": ["mineralogy.rocks", "gemsla.be"]},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(
            set(post.channels.values_list("host", flat=True)),
            {"mineralogy.rocks", "gemsla.be"},
        )

    def test_unknown_channel_slug_is_rejected(self):
        self.client.force_login(self.staff)
        post = self._create_post("Bad Chan", "bad-chan", channels=[self.channel_mr])
        response = self.client.patch(
            f"/blog/post/{post.slug}/",
            {"channel_hosts": ["does-not-exist"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ChannelFilteringTest(BlogApiBaseTest):
    def setUp(self):
        self.gem_post = self._create_post("Gem Only", "gem-only", channels=[self.channel_gem])
        self.mr_post = self._create_post("MR Only", "mr-only", channels=[self.channel_mr])

    def _slugs(self, response):
        return {row["slug"] for row in response.data["results"]}

    def test_filter_by_gemsla_channel(self):
        response = self.client.get("/blog/post/?host=gemsla.be")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._slugs(response), {"gem-only"})

    def test_filter_by_mineralogy_channel_excludes_gemsla(self):
        response = self.client.get("/blog/post/?host=mineralogy.rocks")
        self.assertEqual(self._slugs(response), {"mr-only"})

    def test_default_channel_is_mineralogy_and_excludes_gemsla(self):
        response = self.client.get("/blog/post/")
        self.assertEqual(self._slugs(response), {"mr-only"})


class PublicReadFilteringTest(BlogApiBaseTest):
    def setUp(self):
        self.published = self._create_post("Pub", "pub", channels=[self.channel_mr], is_published=True)
        self.draft = self._create_post("Draft", "draft", channels=[self.channel_mr], is_published=False)

    def _slugs(self, response):
        return {row["slug"] for row in response.data["results"]}

    def test_anonymous_excludes_unpublished(self):
        response = self.client.get("/blog/post/")
        self.assertEqual(self._slugs(response), {"pub"})

    def test_staff_includes_unpublished_for_channel(self):
        self.client.force_login(self.staff)
        response = self.client.get("/blog/post/?host=mineralogy.rocks")
        self.assertEqual(self._slugs(response), {"pub", "draft"})


class PaginationTest(BlogApiBaseTest):
    def setUp(self):
        self.posts = [self._create_post(f"P{index}", f"p-{index}", channels=[self.channel_mr]) for index in range(12)]

    def test_limit_offset_paging(self):
        first = self.client.get("/blog/post/?limit=5")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, first.data)
        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 5)
        self.assertIsNotNone(first.data["next"])

        last = self.client.get("/blog/post/?limit=5&offset=10")
        self.assertEqual(len(last.data["results"]), 2)
        self.assertIsNone(last.data["next"])


class TagsFilterTest(BlogApiBaseTest):
    def setUp(self):
        self.tag_quartz = Tag.objects.create(name="Quartz")
        self.tag_beryl = Tag.objects.create(name="Beryl")
        self.post_a = self._create_post("Has Quartz", "has-quartz", channels=[self.channel_mr])
        self.post_a.tags.set([self.tag_quartz])
        self.post_b = self._create_post("Has Beryl", "has-beryl", channels=[self.channel_mr])
        self.post_b.tags.set([self.tag_beryl])

    def _slugs(self, response):
        return {row["slug"] for row in response.data["results"]}

    def test_filter_by_tag_id(self):
        response = self.client.get(f"/blog/post/?tags={self.tag_quartz.id}")
        self.assertEqual(self._slugs(response), {"has-quartz"})

    def test_filter_by_tag_name_iexact(self):
        response = self.client.get("/blog/post/?tag=quartz")
        self.assertEqual(self._slugs(response), {"has-quartz"})


class SearchTest(BlogApiBaseTest):
    def setUp(self):
        self.sapphire = self._create_post(
            "Sapphire Guide", "sapphire-guide", channels=[self.channel_mr], description="All about blue stones"
        )
        self.emerald = self._create_post(
            "Emerald Basics", "emerald-basics", channels=[self.channel_mr], content="Green beryl deep dive"
        )
        self.tagged = self._create_post("Ruby Notes", "ruby-notes", channels=[self.channel_mr])
        self.tagged.tags.set([Tag.objects.create(name="Corundum")])

    def _slugs(self, response):
        return {row["slug"] for row in response.data["results"]}

    def test_search_matches_name(self):
        response = self.client.get("/blog/post/?q=sapphire")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._slugs(response), {"sapphire-guide"})

    def test_search_matches_description_and_content(self):
        self.assertEqual(self._slugs(self.client.get("/blog/post/?q=blue")), {"sapphire-guide"})
        self.assertEqual(self._slugs(self.client.get("/blog/post/?q=beryl")), {"emerald-basics"})

    def test_search_matches_tag_name(self):
        self.assertEqual(self._slugs(self.client.get("/blog/post/?q=corundum")), {"ruby-notes"})

    def test_search_with_no_match_returns_empty(self):
        response = self.client.get("/blog/post/?q=wrong")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)


class ViewCountTest(BlogApiBaseTest):
    def setUp(self):
        self.post = self._create_post("Viewed", "viewed", channels=[self.channel_mr])

    def test_anonymous_increment_views(self):
        self.assertEqual(self.post.views, 0)
        response = self.client.post(f"/blog/post/{self.post.slug}/increment-views/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["views"], 1)
        self.post.refresh_from_db()
        self.assertEqual(self.post.views, 1)

    def test_increment_views_unknown_slug_404(self):
        response = self.client.post("/blog/post/missing/increment-views/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ContentRoundTripTest(BlogApiBaseTest):
    def setUp(self):
        self.gem = self._create_post(
            "Gem JSON",
            "gem-json",
            channels=[self.channel_gem],
            content="",
            content_json=CONTENT_JSON,
        )
        self.mr = self._create_post(
            "MR MDX",
            "mr-mdx",
            channels=[self.channel_mr],
            content="# Heading\nMDX body",
        )

    def test_gemsla_detail_returns_content_json(self):
        response = self.client.get(f"/blog/post/{self.gem.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content_json"], CONTENT_JSON)

    def test_mineralogy_detail_returns_mdx_content(self):
        response = self.client.get(f"/blog/post/{self.mr.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "# Heading\nMDX body")


class ListShapeTest(BlogApiBaseTest):
    def setUp(self):
        self.post = self._create_post("Lookable", "lookable", channels=[self.channel_mr])

    def test_tag_and_category_lists_return_plain_arrays(self):
        Tag.objects.create(name="PlainTag")
        tags = self.client.get("/blog/tag/")
        self.assertEqual(tags.status_code, status.HTTP_200_OK)
        self.assertIsInstance(tags.data, list)

        categories = self.client.get("/blog/category/")
        self.assertEqual(categories.status_code, status.HTTP_200_OK)
        self.assertIsInstance(categories.data, list)

    def test_post_list_includes_channels_and_cover_image(self):
        response = self.client.get("/blog/post/")
        row = response.data["results"][0]
        self.assertIn("channels", row)
        self.assertIn("cover_image", row)
        self.assertEqual({c["host"] for c in row["channels"]}, {"mineralogy.rocks"})
