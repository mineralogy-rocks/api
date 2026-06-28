from django.core.files.storage import storages

STORE_PRIVATE_STORAGE_ALIAS = "store_private"
STORE_PUBLIC_STORAGE_ALIAS = "store_public"


def store_file(file, name):
    """Save `file` in private store storage; return its stored name."""
    return storages[STORE_PRIVATE_STORAGE_ALIAS].save(name, file)


def signed_url(name):
    """Return a short-lived signed URL for a private store file."""
    return storages[STORE_PRIVATE_STORAGE_ALIAS].url(name)


def public_url(name):
    """Return a stable public URL for a public store asset."""
    if not name:
        return None
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return storages[STORE_PUBLIC_STORAGE_ALIAS].url(name)
