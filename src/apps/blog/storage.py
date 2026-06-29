from django.core.files.storage import storages

BLOG_PUBLIC_STORAGE_ALIAS = "blog_public"


def store_public_file(file, name):
    """Save `file` in public blog storage; return its stored name."""
    return storages[BLOG_PUBLIC_STORAGE_ALIAS].save(name, file)


def public_url(name):
    """Return a stable public URL for a public blog asset."""
    if not name:
        return None
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return storages[BLOG_PUBLIC_STORAGE_ALIAS].url(name)
