# -*- coding: UTF-8 -*-
from django_filters import rest_framework as filters

from .models import Queue


class QueueFilter(filters.FilterSet):
    status = filters.BaseInFilter()

    class Meta:
        model = Queue
        fields = [
            "status",
        ]
