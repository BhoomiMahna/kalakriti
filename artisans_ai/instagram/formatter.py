"""Creative formatting: layout selection + optional brand overlay + Instagram sizing."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image, ImageDraw

from .config import InstagramConfig
from .instagram_schema import LayoutType, PostLayout

logger = logging.getLogger(__name__)

TARGET_SIZE = (1080, 1080)  # 1:1, the safest default across feed placements


class CreativeFormatter:
    def __init__(self, config: InstagramConfig, output_dir: str = "instagram_processed"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format(self, image_paths: list[str], has_video: bool = False) -> PostLayout:
        if not image_paths:
            raise ValueError("At least one image is required to build a post layout.")

        if has_video:
            layout_type = LayoutType.REEL_COVER
        elif len(image_paths) == 1:
            layout_type = LayoutType.SINGLE_IMAGE
        elif 2 <= len(image_paths) <= 10:
            layout_type = LayoutType.CAROUSEL
        else:
            # More than 10 images: Instagram carousel cap. Take the first 10.
            logger.warning("Received %d images, truncating to Instagram's 10-image carousel cap.", len(image_paths))
            image_paths = image_paths[:10]
            layout_type = LayoutType.CAROUSEL

        processed_paths = [self._process_image(p) for p in image_paths]

        return PostLayout(
            layout_type=layout_type,
            media_paths=processed_paths,
            brand_overlay_applied=self.config.ig_apply_brand_overlay,
        )

    def _process_image(self, image_path: str) -> str:
        img = Image.open(image_path).convert("RGB")
        img = self._resize_and_crop(img, TARGET_SIZE)

        if self.config.ig_apply_brand_overlay and self.config.ig_brand_logo_path:
            img = self._apply_brand_overlay(img)
        # If branding isn't configured (your case: no logo yet), we still
        # apply the resize/crop so images meet Instagram's dimension
        # requirements -- just without the watermark/frame.

        out_path = self.output_dir / f"processed_{Path(image_path).name}"
        img.save(out_path, quality=92)
        return str(out_path)

    @staticmethod
    def _resize_and_crop(img: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        target_w, target_h = target_size
        src_w, src_h = img.size
        target_ratio = target_w / target_h
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            # Source is wider than target: crop left/right
            new_width = int(target_ratio * src_h)
            left = (src_w - new_width) // 2
            img = img.crop((left, 0, left + new_width, src_h))
        else:
            # Source is taller than target: crop top/bottom
            new_height = int(src_w / target_ratio)
            top = (src_h - new_height) // 2
            img = img.crop((0, top, src_w, top + new_height))

        return img.resize(target_size, Image.LANCZOS)

    def _apply_brand_overlay(self, img: Image.Image) -> Image.Image:
        """Watermark + accent border. Only runs if a logo path is configured."""
        logo_path = self.config.ig_brand_logo_path
        if not logo_path or not os.path.exists(logo_path):
            logger.warning("ig_apply_brand_overlay is True but no valid logo found at %s; skipping overlay.", logo_path)
            return img

        img = img.copy()
        logo = Image.open(logo_path).convert("RGBA")

        logo_max_w = int(img.width * 0.15)
        ratio = logo_max_w / logo.width
        logo = logo.resize((logo_max_w, int(logo.height * ratio)), Image.LANCZOS)

        margin = int(img.width * 0.03)
        position = (img.width - logo.width - margin, img.height - logo.height - margin)

        base = img.convert("RGBA")
        base.paste(logo, position, logo)

        border_width = max(2, int(img.width * 0.006))
        draw = ImageDraw.Draw(base)
        draw.rectangle(
            [0, 0, img.width - 1, img.height - 1],
            outline=self.config.ig_brand_color,
            width=border_width,
        )

        return base.convert("RGB")
