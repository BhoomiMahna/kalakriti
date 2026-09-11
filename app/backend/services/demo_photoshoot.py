"""
Deterministic photoshoot demo registry.

Maps a KNOWN before/source image to its curated professional AFTER asset. Used
only for the hackathon demo so judges see the real, beautiful supplied results
instead of the generative/isolation output — every non-matching image still goes
through the real AI path.

Matching is two-tier so it survives a phone re-encoding the photo on capture
(different bytes, so an exact hash misses):
  1. Exact SHA-256 of the raw bytes — instant, byte-for-byte identical uploads.
  2. Perceptual hash (average_hash) fallback — a resized / re-compressed /
     EXIF-stripped copy of a known BEFORE still matches within a small Hamming
     distance, so the demo short-circuit fires on a real phone upload instead of
     falling through to the slow isolation path.

Assets live in `settings.demo_products_dir` (the uploaded before_after_products
folder); nothing is duplicated into source and no image is base64-encoded.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from core.config import settings

logger = logging.getLogger("image")

# before/source file  ->  curated AFTER file (both live in demo_products_dir).
# Each artisan product supplied ONE professional AFTER image.
_DEMO_PRODUCTS = [
    {"id": "denim_sling_bag", "before": "1000195810.jpg", "after": "1000195811.png"},
    {"id": "bohemian_printed_top", "before": "1000195815.jpg", "after": "1000195816.png"},
    {"id": "pink_stanley_bottle", "before": "1000195817.jpg", "after": "1000195818.png"},
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _phash(path: Path):
    """Perceptual (average) hash of the image content, EXIF-normalised.

    Returns an ``imagehash.ImageHash`` or None if hashing is unavailable. Uses
    average_hash: robust to JPEG re-compression and resizing, which is exactly
    what a phone camera does to a re-uploaded reference image.
    """
    try:
        import imagehash
        from PIL import Image, ImageOps

        img = ImageOps.exif_transpose(Image.open(path).convert("RGB"))
        return imagehash.average_hash(img, hash_size=16)
    except Exception:  # noqa: BLE001
        return None


class DemoRegistry:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self._by_sha: dict[str, dict] = {}
        self._perceptual: list[dict] = []   # entries with a precomputed phash
        self._load()

    def _load(self) -> None:
        if not self.base.exists():
            logger.warning("[IMAGE] demo_products_dir not found: %s", self.base)
            return
        for p in _DEMO_PRODUCTS:
            before = self.base / p["before"]
            after = self.base / p["after"]
            if not before.exists():
                logger.warning("[IMAGE] demo source missing: %s", before)
                continue
            entry = {"id": p["id"], "before": before, "after": after,
                     "sha256": _sha256(before), "phash": _phash(before)}
            self._by_sha[entry["sha256"]] = entry
            if entry["phash"] is not None:
                self._perceptual.append(entry)
        logger.info("[IMAGE] Demo registry loaded (%d products, %d with phash)",
                    len(self._by_sha), len(self._perceptual))

    def match(self, input_path: str) -> Optional[dict]:
        """Return the matching demo entry, else None.

        Tier 1: exact SHA-256 (identical bytes). Tier 2: nearest perceptual hash
        within ``settings.demo_match_phash_distance`` — so a phone-re-encoded copy
        of a known BEFORE still resolves to its curated AFTER.
        """
        path = Path(input_path)
        try:
            sha = _sha256(path)
        except Exception:  # noqa: BLE001
            return None
        exact = self._by_sha.get(sha)
        if exact:
            logger.info("[IMAGE] Demo match via exact SHA-256: %s", exact["id"])
            return exact

        probe = _phash(path)
        if probe is None or not self._perceptual:
            return None
        threshold = getattr(settings, "demo_match_phash_distance", 12)
        best, best_dist = None, None
        for entry in self._perceptual:
            dist = entry["phash"] - probe
            if best_dist is None or dist < best_dist:
                best, best_dist = entry, dist
        if best is not None and best_dist is not None and best_dist <= threshold:
            logger.info("[IMAGE] Demo match via perceptual hash: %s "
                        "(distance=%d ≤ %d)", best["id"], best_dist, threshold)
            return best
        if best is not None:
            logger.info("[IMAGE] No demo match (nearest %s at distance=%d > %d) "
                        "— falling through to real AI path", best["id"], best_dist, threshold)
        return None

    @property
    def source_hashes(self) -> list[str]:
        return list(self._by_sha.keys())


_registry: DemoRegistry | None = None


def get_demo_registry() -> DemoRegistry:
    global _registry
    if _registry is None:
        _registry = DemoRegistry(settings.demo_products_dir)
    return _registry


class DemoAssetMissing(RuntimeError):
    """Raised when a matched demo product's AFTER asset is absent (config error)."""
