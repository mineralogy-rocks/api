# -*- coding: UTF-8 -*-
from django_filters import rest_framework as filters

from .models import Prompt
from .models import Queue


class QueueFilter(filters.FilterSet):
    status = filters.BaseInFilter()
    code_version__lt = filters.CharFilter(method="filter__code_version__lt", label="Code version <")

    class Meta:
        model = Queue
        fields = [
            "status",
            "code_version__lt",
        ]

    def filter__code_version__lt(self, queryset, name, value):
        major, minor, patch = value.split(".")
        return queryset


class PromptFilter(filters.FilterSet):
    type = filters.BaseInFilter()

    class Meta:
        model = Prompt
        fields = [
            "type",
        ]
