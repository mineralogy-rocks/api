# -*- coding: UTF-8 -*-
from .models import CodeVersion


class CodeVersionMixin(object):
    header_prefix = "HTTP_X_CODE_VERSION"

    def dispatch(self, request, *args, **kwargs):
        request._code_version = self._get_code_version()
        return super().dispatch(request, *args, **kwargs)

    def _get_code_version(self):
        return self.request.META.get(self.header_prefix, None)

    def generate_code_version(self):
        if not self.request._code_version:
            return None
        version, created = CodeVersion.objects.get_or_create(name=self.request._code_version)
        return version
