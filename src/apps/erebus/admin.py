# -*- coding: UTF-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import Queue


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "user",
        "size_display",
        "mime_type",
        "status_display",
        "link",
    ]

    list_display_links = [
        "id",
    ]

    readonly_fields = [
        "size_display",
        "mime_type",
        "created_at",
        "updated_at",
    ]

    def link(self, obj):
        return format_html('<a href="{}" target="_blank">Download</a>', obj.get_absolute_url())

    def size_display(self, obj):
        if obj.size:
            units = ["B", "KB", "MB", "GB", "TB"]
            size = float(obj.size)
            unit_index = 0
            while size >= 1024 and unit_index < len(units) - 1:
                size /= 1024
                unit_index += 1
            return f"{size:.2f} {units[unit_index]}"
        return "-"

    def status_display(self, obj):
        status_colors = {
            Queue.STATUS_QUEUED: "#FFA500",
            Queue.STATUS_PARSED: "#1E90FF",
            Queue.STATUS_PROCESSED: "#32CD32",
            Queue.STATUS_FAILED: "#FF0000",
            Queue.STATUS_ARCHIVED: "#808080",
        }

        color = status_colors.get(obj.status, "#000000")
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())

    status_display.short_description = "Status"
    size_display.short_description = "Size"
