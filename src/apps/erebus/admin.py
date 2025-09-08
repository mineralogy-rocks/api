# -*- coding: UTF-8 -*-
import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms import PromptForm
from .forms import QueueForm
from .models import Chunk
from .models import ChunkIssue
from .models import ChunkResponse
from .models import Prompt
from .models import Queue


@admin.action(description="Mark as archived")
def mark_archived(modeladmin, request, queryset):
    queryset.update(status=Queue.STATUS_ARCHIVED)


@admin.action(description="Schedule for processing")
def schedule_processing(modeladmin, request, queryset):
    queryset.update(status=Queue.STATUS_QUEUED)


class ChunkInline(admin.TabularInline):
    model = Chunk
    extra = 0
    fields = ["hash", "version", "extract_composition", "extract_metadata", "created_at", "responses_count"]
    readonly_fields = [
        "hash",
        "version",
        "created_at",
        "responses_count",
    ]
    can_delete = False
    show_change_link = True

    def responses_count(self, obj):
        return obj.responses.count()

    responses_count.short_description = "Responses"


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    form = QueueForm
    inlines = [ChunkInline]

    list_display = [
        "id",
        "name",
        "owner",
        "size_display",
        "mime_type",
        "status_display",
        "chunks_nr_display",
        "link",
    ]

    list_display_links = [
        "name",
    ]

    readonly_fields = [
        "uuid",
        "size",
        "size_display",
        "mime_type",
        "created_at",
        "updated_at",
        "processed_at",
    ]

    actions = [
        schedule_processing,
        mark_archived,
    ]

    def link(self, obj):
        return format_html('<a href="{}" target="_blank">Download</a>', obj.get_absolute_url())

    def chunks_nr_display(self, obj):
        return obj.chunks.count()

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
            Queue.STATUS_PARSING_FAILED: "#FF0000",
            Queue.STATUS_ARCHIVED: "#808080",
        }

        color = status_colors.get(obj.status, "#000000")
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())

    status_display.short_description = "Status"
    size_display.short_description = "Size (human-friendly)"


@admin.action(description="Mark as approved")
def mark_approved(modeladmin, request, queryset):
    queryset.update(extract_composition=True, extract_metadata=True)


@admin.action(description="Mark as not approved")
def mark_not_approved(modeladmin, request, queryset):
    queryset.update(extract_composition=False, extract_metadata=False)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "hash",
        "parent",
        "version",
        "extract_composition",
        "extract_metadata",
        "_code_version",
        "created_at",
        "responses_count",
    ]

    list_display_links = [
        "hash",
    ]

    list_filter = [
        "extract_composition",
        "extract_metadata",
        "version",
        "parent",
    ]

    search_fields = [
        "hash",
        "parent__name",
    ]

    readonly_fields = [
        "created_at",
        "_code_version",
    ]

    actions = [
        mark_approved,
        mark_not_approved,
    ]

    def _code_version(self, obj):
        return obj.code_version.version if obj.code_version else None

    def responses_count(self, obj):
        return obj.responses.count()

    _code_version.short_description = "Code version"
    responses_count.short_description = "Responses"


@admin.action(description="Mark as resolved")
def mark_resolved(modeladmin, request, queryset):
    queryset.update(is_resolved=True)


@admin.action(description="Mark as unresolved")
def mark_unresolved(modeladmin, request, queryset):
    queryset.update(is_resolved=False)


@admin.register(ChunkIssue)
class ChunkIssueAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "chunk",
        "email",
        "user",
        "is_resolved",
        "created_at",
        "resolved_at",
    ]

    list_display_links = [
        "name",
    ]

    list_filter = [
        "is_resolved",
        "chunk",
        "user",
    ]

    search_fields = [
        "name",
        "comment",
        "email",
        "chunk__name",
    ]

    readonly_fields = [
        "created_at",
        "resolved_at",
    ]

    actions = [
        mark_resolved,
        mark_unresolved,
    ]


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    form = PromptForm
    list_display = [
        "id",
        "type",
        "text_preview",
        "created_at",
    ]

    list_filter = [
        "type",
    ]

    search_fields = [
        "text",
    ]

    readonly_fields = [
        "created_at",
    ]

    def text_preview(self, obj):
        if obj.text:
            return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text
        return "-"

    text_preview.short_description = "Text Preview"


@admin.register(ChunkResponse)
class ChunkResponseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "chunk",
        "prompt",
        "is_extracted",
        "is_error",
        "response_preview",
        "exception_preview",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "is_extracted",
        "is_error",
        "chunk",
        "prompt",
    ]

    search_fields = [
        "chunk__name",
        "response",
        "exception",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
        "formatted_clean_response",
    ]

    def response_preview(self, obj):
        if obj.response:
            return obj.response[:100] + "..." if len(obj.response) > 100 else obj.response
        return "-"

    def exception_preview(self, obj):
        if obj.exception:
            return obj.exception[:100] + "..." if len(obj.exception) > 100 else obj.exception
        return "-"

    def formatted_clean_response(self, obj):
        if obj.clean_response:
            try:
                formatted_json = json.dumps(obj.clean_response, indent=4)
                return mark_safe(f"<pre>{formatted_json}</pre>")
            except Exception as e:
                return f"Error formatting JSON: {str(e)}"
        return "-"

    response_preview.short_description = "Response Preview"
    exception_preview.short_description = "Exception Preview"
    formatted_clean_response.short_description = "Formatted Clean Response"
