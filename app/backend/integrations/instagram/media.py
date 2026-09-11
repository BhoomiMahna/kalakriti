"""
Media uploader seam: local processed image path -> publicly reachable URL.

The Instagram Graph API can only fetch public URLs. Here we copy the processed
image into the app's served storage and return `{api_base_url}/media/<name>`.
This is deliberately behind one function so it can be swapped for real object
storage (S3 / GCS / Cloudinary) without touching the pipeline.

NOTE: in local dev the public URL is http://localhost — reachable for the demo
preview, but NOT reachable by Meta's servers. Real publishing needs a genuinely
public `API_BASE_URL` (a deploy or a tunnel) or an object-storage uploader.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from core.config import settings

STORAGE = Path(settings.storage_dir)


def to_public_url(local_path: str) -> str:
    """Copy `local_path` into served storage and return its public URL."""
    src = Path(local_path)
    STORAGE.mkdir(parents=True, exist_ok=True)
    # If already inside storage, reuse; else copy in with a unique name.
    if src.resolve().parent == STORAGE.resolve():
        name = src.name
    else:
        name = f"ig_{uuid.uuid4().hex}{src.suffix or '.jpg'}"
        shutil.copyfile(src, STORAGE / name)
    return f"{settings.api_base_url.rstrip('/')}/media/{name}"


def make_media_uploader():
    """Return the Callable[[str], str] the pipeline expects."""
    return to_public_url
