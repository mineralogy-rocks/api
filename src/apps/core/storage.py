from django.core.files.storage import storages
from django.utils.text import get_valid_filename

MEDIA_STORAGE_ALIAS = "media"


def _is_absolute_url(name):
    return str(name).startswith(("http://", "https://"))


def _prefixed_name(prefix, name):
    filename = get_valid_filename(str(name).split("/")[-1])
    return f"{prefix.strip('/')}/{filename}"


def _storage_name(prefix, name):
    value = str(name).lstrip("/")
    root = prefix.strip("/").split("/")[0]
    if value.startswith(f"{root}/"):
        return value
    return f"{prefix.strip('/')}/{value}"


def store_file(file, name, prefix):
    """Save `file` in private media storage under `prefix`; return its stored name."""
    return storages[MEDIA_STORAGE_ALIAS].save(_prefixed_name(prefix, name), file)


def signed_url(name, prefix):
    """Return a short-lived signed URL for a media file stored under `prefix`."""
    if not name:
        return None
    if _is_absolute_url(name):
        return name
    return storages[MEDIA_STORAGE_ALIAS].url(_storage_name(prefix, name))
