# -*- coding: UTF-8 -*-
from core.models.base import BaseModel
from core.models.base import Creatable
from core.models.base import Nameable
from core.models.base import Updatable
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Tag(BaseModel, Nameable):
    class Meta:
        ordering = ["id"]

        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name


class Category(BaseModel, Nameable):
    slug = models.SlugField(max_length=200, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["id"]

        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Post(BaseModel, Nameable, Creatable, Updatable):
    slug = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    description = models.CharField(max_length=200)
    content = models.TextField()

    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)

    tags = models.ManyToManyField(Tag, related_name="posts")
    authors = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="posts", blank=True)
    category = models.ForeignKey(Category, related_name="posts", on_delete=models.SET_NULL, null=True)

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]

        verbose_name = "Post"
        verbose_name_plural = "Posts"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/blog/{self.slug}/"

    def clean(self):
        if self.is_published and not self.published_at:
            raise ValidationError({"published_at": "Published date is required for published posts."})
        if self.is_published and not self.slug:
            raise ValidationError({"slug": "Slug is required for published posts."})
        return super().clean()
