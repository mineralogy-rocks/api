# -*- coding: UTF-8 -*-
from django_filters import rest_framework as filters

from .models import Post


class PostFilter(filters.FilterSet):
    category = filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
    )
    author = filters.NumberFilter(field_name="authors__id", lookup_expr="exact")
    tag = filters.CharFilter(field_name="tags__name", lookup_expr="iexact")

    class Meta:
        model = Post
        fields = ["name", "views", "likes", "tags", "category", "author", "tag"]
