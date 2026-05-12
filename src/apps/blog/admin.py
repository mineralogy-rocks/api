# -*- coding: UTF-8 -*-
from django.contrib import admin
from django.db.models import Count

from .models import Category
from .models import Post
from .models import Tag


class PostCountMixin(object):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_posts=Count("posts"))
        return queryset

    @admin.display(description="Posts")
    def _posts(self, instance):
        return instance._posts


@admin.register(Category)
class CategoryAdmin(PostCountMixin, admin.ModelAdmin):
    list_display = ["id", "name", "slug", "_posts"]
    search_fields = ["name"]


@admin.register(Tag)
class TagAdmin(PostCountMixin, admin.ModelAdmin):
    list_display = ["id", "name", "_posts"]
    search_fields = ["name"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"

    list_display = [
        "id",
        "name",
        "category",
        "tags_",
        "is_published",
        "published_at",
    ]
    list_filter = [
        "is_published",
        "category",
        "tags",
    ]

    list_display_links = ["name"]
    filter_horizontal = ("tags", "authors")

    readonly_fields = [
        "id",
        "views",
        "likes",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        (None, {"fields": ["id", "name", "slug", "is_published"]}),
        ("Description", {"fields": ["description"], "classes": ["full-width"]}),
        ("Content", {"fields": ["content"], "classes": ["full-width", "full-height"]}),
        ("Context", {"fields": ["category", "tags", "authors"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
        (
            "Metadata",
            {
                "fields": [
                    "views",
                    "likes",
                    "published_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Tags")
    def tags_(self, instance):
        if instance.tags:
            return ", ".join([tag.name for tag in instance.tags.all()])
