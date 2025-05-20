# -*- coding: UTF-8 -*-
from django import forms
from django.core.validators import FileExtensionValidator

from .models import Queue


class QueueForm(forms.ModelForm):
    class Meta:
        model = Queue
        fields = [
            "owner",
            "name",
            "description",
            "file",
            "size",
            "mime_type",
            "status",
        ]

    def clean_file(self):
        file = self.cleaned_data["file"]

        if file.size > Queue.MAX_SIZE_ALLOWED:
            raise forms.ValidationError("File size exceeds 10MB limit")

        FileExtensionValidator(allowed_extensions=Queue.ALLOWED_EXTENSIONS)
        return file
