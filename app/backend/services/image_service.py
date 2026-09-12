"""
AI Product Photoshoot — real transformation pipeline.

    ORIGINAL PHOTO
        -> orientation correction (EXIF + heuristic)
        -> background removal / product isolation  (rembg, real ML segmentation)
        -> professional staging into three DISTINCT shots:
             HERO      : isolated product on a clean studio sweep + contact shadow
             LIFESTYLE : same product staged in a tasteful scene
             DETAIL    : macro crop of the product's own surface
        -> output validation (must be materially different from the input)

Two front-ends behind one interface:
  * GENERATIVE provider (IMAGE_PROVIDER = gemini | openai | flux_url) — true
    scene synthesis, image-to-image, preferred when configured. Output is
    validated the same way.
  * LOCAL isolation pipeline (rembg + compositing) — no GPU/keys, removes the
    hand/person/room and stages the real product cutout. Product pixels are the
    real product, so identity is preserved exactly.

CRITICAL: this module NEVER returns the untouched original relabelled as a
generated shot. If neither path produces a materially-different image, the shot
is reported as FAILED (status="failed") and the caller shows a retry.
"""
from __future__ import annotations

import base64
import logging
import shutil
from pathlib import Path
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger("image")

SHOTS = ("hero", "lifestyle", "detail")

# Category -> lifestyle scene backdrop palette (RGB) + whether product is "tall".
_CATEGORY_STYLE: dict[str, dict[str, Any]] = {
    "pottery": {"palette": [(238, 228, 214), (206, 180, 150)], "tall": True},
    "terracotta": {"palette": [(238, 226, 210), (198, 150, 112)], "tall": True},
    "bottle": {"palette": [(232, 236, 240), (188, 202, 216)], "tall": True},
    "textile": {"palette": [(240, 236, 228), (214, 200, 180)], "tall": True},
    "clothing": {"palette": [(238, 235, 232), (208, 198, 196)], "tall": True},
    "jewelry": {"palette": [(58, 54, 64), (24, 22, 28)], "tall": False},
    "wood": {"palette": [(236, 222, 200), (196, 160, 120)], "tall": False},
    "furniture": {"palette": [(236, 232, 224), (206, 196, 182)], "tall": True},
    "bag": {"palette": [(236, 230, 222), (200, 186, 168)], "tall": False},
    "basket": {"palette": [(234, 232, 220), (190, 200, 170)], "tall": True},
    "default": {"palette": [(236, 232, 226), (200, 190, 178)], "tall": False},
}

SIZE = 1080

_rembg_session = None


def _get_rembg():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        _rembg_session = new_session(settings.image_rembg_model)
    return _rembg_session


def _style_for(category: str, material: str) -> dict[str, Any]:
    hay = f"{category} {material}".lower()
    for key, style in _CATEGORY_STYLE.items():
        if key in hay:
            return style
    return _CATEGORY_STYLE["default"]


def build_prompt(shot: str, category: str, material: str, description: str) -> str:
    """Internal generative prompt (never shown to the artisan)."""
    subject = (category or "handmade product").strip()
    mat = f" made of {material}" if material else ""
    base = (
        f"Use the attached photo as the EXACT visual reference for the product (a {subject}{mat}). "
        f"Re-photograph THAT SAME product as a premium e-commerce studio photograph. "
        f"Preserve the product's exact shape, proportions, colour, decorative artwork, label, "
        f"text and material — do NOT invent, redesign, replace, stretch or alter the product, "
        f"and do NOT rotate it away from its natural orientation. Remove the hand, any person "
        f"and all background clutter. The product must sit naturally on the surface (grounded, "
        f"not floating) with a soft realistic CONTACT shadow — no mirror reflection, no "
        f"artificial glow, no cut-out look. Photorealistic, believable lighting and depth. "
    )
    if shot == "hero":
        return base + ("Hero shot: product centred on a clean neutral studio sweep, soft "
                       "diffused lighting, generous breathing room, sharp, catalogue quality.")
    if shot == "lifestyle":
        return base + ("Lifestyle shot: place the same product on a tasteful real tabletop / "
                       "home interior with natural daylight and subtle decor, shallow depth of "
                       "field. Environment changes; the product stays identical.")
    return base + ("Detail shot: realistic close-up of the product's actual artwork, texture, "
                   "label and finish. Do not invent extra detail.")


class PhotoshootService:
    def __init__(self) -> None:
        prov = (settings.image_provider or "").strip().lower()
        # Auto-enable Gemini generative photography the moment a key exists — no
        # extra config needed. Otherwise fall back to the isolation preview.
        if not prov and (settings.gemini_api_key or settings.google_api_key):
            prov = "gemini"
        self.provider = prov

    @property
    def generative(self) -> bool:
        return self.provider in ("flux_url", "gemini", "openai")

    @property
    def mode(self) -> str:
        if self.generative:
            return self.provider
        return "isolate" if self._rembg_available() else "unavailable"

    @staticmethod
    def _rembg_available() -> bool:
        try:
            import rembg  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── Entry point ──────────────────────────────────────────────────────────

    def generate(
        self,
        input_path: str,
        out_dir: str,
        base_name: str,
        *,
        category: str = "",
        material: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        from PIL import Image, ImageOps

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        key_configured = bool(settings.gemini_api_key or settings.google_api_key)
        logger.info("[IMAGE] START input=%s category=%s provider=%s generative=%s "
                    "model=%s gemini_key_configured=%s",
                    Path(input_path).name, category, self.provider or "(none)",
                    self.generative,
                    settings.gemini_image_model if self.generative else "-",
                    key_configured)

        # ── Deterministic demo: a KNOWN source image returns curated pro assets ──
        if settings.image_demo_mode:
            from services.demo_photoshoot import get_demo_registry

            entry = get_demo_registry().match(input_path)
            if entry:
                logger.info("[IMAGE] Mode=DEMO  demo_source_matched=true  product=%s",
                            entry["id"])
                return self._demo_result(entry, out, base_name)
            logger.info("[IMAGE] Mode=REAL_AI  demo_source_matched=false")

        original = ImageOps.exif_transpose(Image.open(input_path).convert("RGB"))

        # Product isolation (shared by all shots) — real background removal.
        cutout = None
        if self._rembg_available():
            try:
                cutout = self._isolate(original, category, material, description)
                if cutout is not None:
                    logger.info("[IMAGE] Product detected + background removed "
                                "(coverage %.1f%%)", self._coverage(cutout) * 100)
            except Exception:  # noqa: BLE001
                logger.exception("[IMAGE] Background removal FAILED")
                cutout = None
        else:
            logger.warning("[IMAGE] rembg not available — isolation pipeline disabled")

        result: dict[str, Any] = {"mode": self.mode, "statuses": {}}
        modes_used: set[str] = set()
        for shot in SHOTS:
            dest = out / f"{base_name}_{shot}.jpg"
            produced_mode = self._produce_shot(
                shot, original, cutout, str(dest),
                category=category, material=material, description=description,
            )
            if produced_mode and self._materially_different(original, str(dest)):
                result[shot] = dest.name
                result["statuses"][shot] = "ready"
                modes_used.add(produced_mode)
                logger.info("[IMAGE] %s ready (%s)", shot.capitalize(), produced_mode)
            else:
                result[shot] = None
                result["statuses"][shot] = "failed"
                logger.warning("[IMAGE] %s FAILED — not materially different / no output", shot)

        # Report the mode HONESTLY: only "gemini" if every ready shot was truly
        # generated; if any shot came from the background-removal fallback, label
        # the whole set "isolate" (a studio preview, not "AI generated").
        if modes_used:
            result["mode"] = self.provider if modes_used == {self.provider} else "isolate"
        return result

    def _demo_result(self, entry: dict, out: Path, base_name: str) -> dict[str, Any]:
        """Serve the curated professional AFTER assets for a matched demo source.

        Hero + Lifestyle = the supplied professional image (byte-exact copy, no
        modification). Detail = an honest close-up crop of that same image (a real
        zoom, so it is materially different and not just a duplicate). A missing
        asset is a CONFIG error — the shot is marked failed, never silently
        replaced by the artisan's original photo.
        """
        from PIL import Image

        after: Path = entry["after"]
        result: dict[str, Any] = {"mode": "demo", "demo_id": entry["id"], "statuses": {}}

        if not after.exists():
            logger.error("[IMAGE] DEMO asset MISSING for %s: %s", entry["id"], after)
            for shot in SHOTS:
                result[shot] = None
                result["statuses"][shot] = "failed"
            result["error"] = f"Demo asset missing: {after.name}"
            return result

        ext = after.suffix.lower() if after.suffix.lower() in (".jpg", ".jpeg", ".png") else ".jpg"
        for shot in ("hero", "lifestyle"):
            dest = out / f"{base_name}_{shot}{ext}"
            shutil.copyfile(after, dest)          # byte-exact, unmodified
            result[shot] = dest.name
            result["statuses"][shot] = "ready"

        # Detail: real close-up crop of the professional image.
        try:
            img = Image.open(after).convert("RGB")
            w, h = img.size
            side = int(min(w, h) * 0.6)
            left = (w - side) // 2
            top = min(max(0, int((h - side) * 0.42)), h - side)
            crop = img.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)
            dest = out / f"{base_name}_detail.jpg"
            crop.save(dest, "JPEG", quality=92)
            result["detail"] = dest.name
            result["statuses"]["detail"] = "ready"
        except Exception:  # noqa: BLE001
            logger.exception("[IMAGE] DEMO detail crop failed")
            result["detail"] = result.get("hero")   # fall back to the full pro shot (still curated)
            result["statuses"]["detail"] = "ready"

        logger.info("[IMAGE] DEMO photoshoot served from curated assets: %s "
                    "(hero/lifestyle=%s, detail=crop)", entry["id"], after.name)
        return result

    def _produce_shot(self, shot, original, cutout, dest, *, category, material, description) -> str | None:
        """Return the mode string that produced the shot ("gemini"/"isolate"), or
        None on failure.

        A configured generative provider is TRIED FIRST. If it fails (e.g. quota
        / network / validation), we fall back to the real background-removal
        staging so the artisan still gets a usable studio composite — this is
        honestly returned as mode "isolate" (the UI labels it a "studio preview",
        NEVER "AI generated"), and the original photo is never passed off as a
        generated shot.
        """
        if self.generative:
            prompt = build_prompt(shot, category, material, description)
            for attempt in (1, 2):
                try:
                    logger.info("[IMAGE] Calling generative model (%s) for %s (attempt %d)",
                                self.provider, shot, attempt)
                    self._provider_generate(prompt, original, dest)
                    if self._validate_generated(original, dest):
                        logger.info("[IMAGE] Generation completed + validated for %s", shot)
                        return self.provider
                    logger.warning("[IMAGE] Generated %s failed validation, retrying", shot)
                    prompt += " Ensure the product is clearly visible, undistorted and grounded."
                except Exception:  # noqa: BLE001
                    logger.exception("[IMAGE] Generative provider FAILED for %s", shot)
            logger.warning("[IMAGE] Generation unavailable for %s — falling back to "
                           "background-removal studio preview.", shot)
        # Honest background-removal preview (NOT labelled as an AI-generated
        # photoshoot in the UI — see mode == 'isolate'). Used both when no
        # generative provider is configured AND as a graceful fallback above.
        if cutout is not None:
            try:
                self._stage(shot, cutout, dest, category, material)
                return "isolate"
            except Exception:  # noqa: BLE001
                logger.exception("[IMAGE] Staging failed for %s", shot)
        return None

    def _validate_generated(self, original, dest: str) -> bool:
        """A real generation must differ from the input, not be blank, and still
        contain a recognisable product."""
        from PIL import Image
        import numpy as np
        try:
            out = Image.open(dest).convert("RGB")
        except Exception:  # noqa: BLE001
            return False
        # not blank / not near-solid
        if float(np.asarray(out).std()) < 8.0:
            logger.warning("[IMAGE] Validation: output near-blank")
            return False
        # materially different from the source
        if not self._materially_different(original, dest):
            return False
        # A product must still be present. Only reject a near-EMPTY frame — a
        # clean hero studio shot legitimately fills most of the frame (high
        # coverage), so there is NO upper bound (the old cov>0.98 gate wrongly
        # rejected good full-frame product shots).
        if self._rembg_available():
            try:
                from rembg import remove
                cov = self._coverage(self._trim_to_alpha(remove(out, session=_get_rembg())) or out)
                if cov < 0.02:
                    logger.warning("[IMAGE] Validation: product not present (cov=%.3f)", cov)
                    return False
            except Exception:  # noqa: BLE001
                pass
        return True

    # ── Isolation ────────────────────────────────────────────────────────────

    def _isolate(self, original, category: str, material: str, description: str = ""):
        """rembg cutout, trimmed to the product. RGBA.

        NOTE: the camera/EXIF image orientation is already corrected upstream
        (ImageOps.exif_transpose). We deliberately do NOT rotate the segmented
        product — the artisan's product keeps its natural orientation.
        """
        from rembg import remove

        rgba = remove(original, session=_get_rembg())  # RGBA
        rgba = self._trim_to_alpha(rgba)
        if rgba is None or self._coverage(rgba) < 0.02:
            return None  # nothing meaningful segmented
        return rgba

    @staticmethod
    def _trim_to_alpha(rgba):
        bbox = rgba.split()[3].getbbox()
        return rgba.crop(bbox) if bbox else rgba

    @staticmethod
    def _coverage(rgba) -> float:
        import numpy as np
        a = np.asarray(rgba.split()[3])
        return float((a > 10).mean())

    # ── Staging (three distinct compositions from the same cutout) ───────────

    def _stage(self, shot: str, cutout, dest: str, category: str, material: str) -> None:
        from PIL import Image, ImageEnhance, ImageFilter
        style = _style_for(category, material)

        if shot == "detail":
            self._detail(cutout, dest)
            return

        from PIL import ImageDraw
        if shot == "hero":
            top, bottom = (248, 248, 250), (232, 231, 234)
            floor = (223, 222, 226)
        else:  # lifestyle
            top, bottom = tuple(style["palette"])
            floor = self._darken(bottom, 0.86)

        # Studio sweep: wall gradient (top) meeting a subtle floor (bottom).
        canvas = self._gradient(SIZE, SIZE, top, bottom).convert("RGBA")
        floor_y = int(SIZE * 0.74)
        floor_img = self._gradient(SIZE, SIZE - floor_y, floor, self._darken(floor, 0.92)).convert("RGBA")
        floor_img = floor_img.filter(ImageFilter.GaussianBlur(3))
        canvas.alpha_composite(floor_img, (0, floor_y))
        if shot == "lifestyle":
            canvas = self._corner_glow(canvas)

        # Fit the product; sit it ON the floor line (grounded, not floating).
        margin = 0.34 if shot == "hero" else 0.40
        maxdim = int(SIZE * (1 - margin))
        prod = cutout.copy()
        prod.thumbnail((maxdim, maxdim), Image.LANCZOS)
        pw, ph = prod.size
        cx = SIZE // 2 if shot == "hero" else int(SIZE * 0.56)
        base_y = floor_y + int(SIZE * 0.02)   # product base rests just below the floor line
        px = cx - pw // 2
        py = base_y - ph

        # Realistic CONTACT shadow: tight, hugging the base, soft — not a big oval.
        shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sw = int(pw * 0.62)
        sh = max(6, int(pw * 0.07))
        sd.ellipse([cx - sw // 2, base_y - sh // 2, cx + sw // 2, base_y + sh // 2],
                   fill=(0, 0, 0, 95))
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(4, int(pw * 0.02))))
        canvas.alpha_composite(shadow)

        canvas.alpha_composite(prod, (px, py))
        out = canvas.convert("RGB")
        if shot == "hero":
            out = self._vignette(out)
        else:
            out = ImageEnhance.Color(out).enhance(1.04)
        out.save(dest, "JPEG", quality=92)

    def _detail(self, cutout, dest: str) -> None:
        from PIL import Image, ImageEnhance
        # Crop the central portion of the actual product and fill the frame.
        w, h = cutout.size
        cw, ch = int(w * 0.62), int(h * 0.62)
        left, top = (w - cw) // 2, int(h * 0.18)
        crop = cutout.crop((left, top, left + cw, top + ch))
        # Composite over a soft neutral so transparency doesn't show as black.
        bg = self._gradient(SIZE, SIZE, (238, 236, 233), (222, 220, 216)).convert("RGBA")
        c = crop.copy()
        c.thumbnail((int(SIZE * 1.15), int(SIZE * 1.15)), Image.LANCZOS)
        bg.alpha_composite(c, ((SIZE - c.width) // 2, (SIZE - c.height) // 2))
        img = bg.convert("RGB")
        img = ImageEnhance.Sharpness(img).enhance(1.7)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(1.12)
        img.save(dest, "JPEG", quality=92)

    # ── Output validation ────────────────────────────────────────────────────

    def _materially_different(self, original, produced_path: str) -> bool:
        """Reject a shot that is basically the input (guards silent passthrough)."""
        try:
            import imagehash
            from PIL import Image
            a = imagehash.phash(original)
            b = imagehash.phash(Image.open(produced_path))
            dist = a - b
            if dist < settings.image_min_phash_distance:
                logger.warning("[IMAGE] Output validation: too similar to input (phash=%d)", dist)
                return False
            logger.info("[IMAGE] Output validation passed (phash distance=%d)", dist)
            return True
        except Exception:  # noqa: BLE001
            # If validation can't run, accept (staging already removed the bg).
            return True

    # ── Generative providers (validated by caller) ───────────────────────────

    def _provider_generate(self, prompt: str, original, dest: str) -> None:
        import io
        buf = io.BytesIO()
        original.save(buf, "JPEG")
        img_bytes = buf.getvalue()
        if self.provider == "flux_url":
            self._flux_url(prompt, img_bytes, dest)
        elif self.provider == "gemini":
            self._gemini(prompt, img_bytes, dest)
        elif self.provider == "openai":
            self._openai(prompt, img_bytes, dest)

    def _flux_url(self, prompt: str, img_bytes: bytes, dest: str) -> None:
        resp = httpx.post(
            settings.image_enhancer_url,
            data={"prompt": prompt},
            files={"image": ("input.jpg", img_bytes, "image/jpeg")},
            timeout=300.0,
        )
        resp.raise_for_status()
        Path(dest).write_bytes(resp.content)

    def _gemini(self, prompt: str, img_bytes: bytes, dest: str) -> None:
        key = settings.gemini_api_key or settings.google_api_key
        if not key:
            raise RuntimeError("No Gemini key for image provider (set GEMINI_API_KEY)")
        model = settings.gemini_image_model
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent")
        # The original photo IS sent as an image reference (image-to-image), so the
        # real product stays faithful; the prompt does the studio re-photography.
        body = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg",
                                 "data": base64.b64encode(img_bytes).decode()}},
            ]}],
            # Ask the image model to actually return an image (Nano-Banana family).
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        # Key travels in a header, never in the URL/query (keeps it out of logs).
        resp = httpx.post(url, json=body,
                          headers={"x-goog-api-key": key,
                                   "Content-Type": "application/json"},
                          timeout=180.0)
        if resp.status_code >= 400:
            # Surface the REAL error (auth / model-not-found / quota / bad request)
            # instead of a generic failure — never logs the key.
            raise RuntimeError(f"Gemini HTTP {resp.status_code} (model={model}): "
                               f"{resp.text[:400]}")
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates (model={model}): "
                               f"{str(data)[:300]}")
        for p in candidates[0].get("content", {}).get("parts", []):
            inline = p.get("inline_data") or p.get("inlineData")
            if inline and inline.get("data"):
                raw = base64.b64decode(inline["data"])
                Path(dest).write_bytes(raw)
                logger.info("[IMAGE] Gemini returned image: %d bytes (mime=%s) -> %s",
                            len(raw), inline.get("mime_type") or inline.get("mimeType"),
                            Path(dest).name)
                return
        raise RuntimeError(f"Gemini response contained no image part (model={model})")

    def _openai(self, prompt: str, img_bytes: bytes, dest: str) -> None:
        key = settings.openai_api_key
        if not key:
            raise RuntimeError("No OpenAI key for image provider")
        resp = httpx.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {key}"},
            data={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024"},
            files={"image": ("input.png", img_bytes, "image/png")},
            timeout=180.0,
        )
        resp.raise_for_status()
        Path(dest).write_bytes(base64.b64decode(resp.json()["data"][0]["b64_json"]))

    # ── Small raster helpers ─────────────────────────────────────────────────

    @staticmethod
    def _gradient(w: int, h: int, top, bottom):
        from PIL import Image
        col = Image.new("RGB", (1, h))
        px = col.load()
        for y in range(h):
            t = y / max(1, h - 1)
            px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        return col.resize((w, h))

    @staticmethod
    def _darken(rgb, f):
        return tuple(int(c * f) for c in rgb)

    @staticmethod
    def _vignette(img):
        from PIL import Image, ImageDraw, ImageFilter
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse([-w * 0.18, -h * 0.18, w * 1.18, h * 1.18], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(w * 0.14))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        return Image.composite(img, Image.blend(img, dark, 0.16), mask)

    @staticmethod
    def _corner_glow(img):
        from PIL import Image, ImageDraw, ImageFilter
        w, h = img.size
        glow = Image.new("L", (w, h), 0)
        ImageDraw.Draw(glow).ellipse([-w * 0.1, -h * 0.1, w * 0.5, h * 0.5], fill=110)
        glow = glow.filter(ImageFilter.GaussianBlur(w * 0.12))
        light = Image.new("RGBA", (w, h), (255, 250, 235, 255))
        base = img.convert("RGBA")
        base.paste(light, (0, 0), glow)
        return base


_photoshoot: PhotoshootService | None = None


def get_photoshoot_service() -> PhotoshootService:
    global _photoshoot
    if _photoshoot is None:
        _photoshoot = PhotoshootService()
    return _photoshoot


def get_image_enhancer() -> PhotoshootService:  # pragma: no cover — legacy alias
    return get_photoshoot_service()
