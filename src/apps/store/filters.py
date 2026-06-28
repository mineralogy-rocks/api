# -*- coding: UTF-8 -*-
from django_filters import rest_framework as filters

from .models import Report
from .models import Stone


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class StoneFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="selling_price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="selling_price", lookup_expr="lte")

    min_weight = filters.NumberFilter(field_name="weight_carats", lookup_expr="gte")
    max_weight = filters.NumberFilter(field_name="weight_carats", lookup_expr="lte")

    color = NumberInFilter(field_name="color_id", lookup_expr="in")
    cut = NumberInFilter(field_name="cut_id", lookup_expr="in")
    treatment = filters.NumberFilter(field_name="treatment_id")
    untreated = filters.BooleanFilter(method="filter_untreated")

    is_sold = filters.BooleanFilter()

    class Meta:
        model = Stone
        fields = [
            "min_price",
            "max_price",
            "min_weight",
            "max_weight",
            "color",
            "cut",
            "treatment",
            "untreated",
            "is_sold",
        ]

    def filter_untreated(self, queryset, name, value):
        if value:
            return queryset.filter(treatment__slug="untreated")
        return queryset


class ReportFilter(filters.FilterSet):
    public = filters.BooleanFilter()
    unlinked = filters.BooleanFilter(method="filter_unlinked")

    class Meta:
        model = Report
        fields = ["public", "unlinked"]

    def filter_unlinked(self, queryset, name, value):
        if value:
            return queryset.filter(linked_stone__isnull=True)
        return queryset
