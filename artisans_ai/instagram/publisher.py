"""Thin wrapper around the Instagram Graph API (content publishing + insights)."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from .config import InstagramConfig
from .instagram_schema import EngagementMetrics, InstagramCaption, LayoutType, PostLayout

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


class InstagramAPIError(RuntimeError):
    pass


class InstagramPublisher:
    """
    Requires: a Meta Business Account, an Instagram Professional Account
    linked to it, and a registered Facebook App with `instagram_content_publish`
    and `instagram_manage_insights` permissions (see package README).
    """

    def __init__(self, config: InstagramConfig, session: Optional[requests.Session] = None):
        self.config = config
        self.session = session or requests.Session()

    # ── Publishing ──────────────────────────────────────────────────────

    def create_media_container(
        self,
        image_url: str,
        caption: InstagramCaption,
        is_carousel_item: bool = False,
    ) -> str:
        """Uploads/registers an image and returns a media container ID."""
        url = f"{GRAPH_API_BASE}/{self.config.ig_business_account_id}/media"
        params = {
            "image_url": image_url,
            "access_token": self.config.ig_access_token,
        }
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        else:
            params["caption"] = caption.full_text

        data = self._post_with_retries(url, params)
        return data["id"]

    def create_carousel_container(
        self,
        child_container_ids: list[str],
        caption: InstagramCaption,
    ) -> str:
        url = f"{GRAPH_API_BASE}/{self.config.ig_business_account_id}/media"
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(child_container_ids),
            "caption": caption.full_text,
            "access_token": self.config.ig_access_token,
        }
        data = self._post_with_retries(url, params)
        return data["id"]

    def publish_container(self, container_id: str) -> str:
        """Publishes a media container and returns the published post ID."""
        url = f"{GRAPH_API_BASE}/{self.config.ig_business_account_id}/media_publish"
        params = {
            "creation_id": container_id,
            "access_token": self.config.ig_access_token,
        }
        data = self._post_with_retries(url, params)
        return data["id"]

    def publish(self, layout: PostLayout, caption: InstagramCaption, image_urls: list[str]) -> str:
        """
        High-level publish flow. `image_urls` must be publicly reachable URLs
        (Graph API requires this) corresponding 1:1 with layout.media_paths --
        you'll need to upload processed images to your own CDN/storage first
        and pass their public URLs here.
        """
        if len(image_urls) != len(layout.media_paths):
            raise ValueError("image_urls must have one public URL per processed media path.")

        if layout.layout_type == LayoutType.CAROUSEL:
            child_ids = [
                self.create_media_container(url, caption, is_carousel_item=True)
                for url in image_urls
            ]
            container_id = self.create_carousel_container(child_ids, caption)
        else:
            container_id = self.create_media_container(image_urls[0], caption)

        return self.publish_container(container_id)

    # ── Insights ────────────────────────────────────────────────────────

    def get_post_insights(self, instagram_post_id: str) -> EngagementMetrics:
        url = f"{GRAPH_API_BASE}/{instagram_post_id}/insights"
        params = {
            "metric": "likes,comments,shares,saved,reach,impressions",
            "access_token": self.config.ig_access_token,
        }
        data = self._get_with_retries(url, params)

        values = {item["name"]: item["values"][0]["value"] for item in data.get("data", [])}
        return EngagementMetrics(
            instagram_post_id=instagram_post_id,
            likes=values.get("likes", 0),
            comments=values.get("comments", 0),
            shares=values.get("shares", 0),
            saves=values.get("saved", 0),
            reach=values.get("reach", 0),
            impressions=values.get("impressions", 0),
        )

    # ── HTTP helpers with retry/backoff for rate limits ────────────────

    def _post_with_retries(self, url: str, params: dict) -> dict:
        return self._request_with_retries("POST", url, params)

    def _get_with_retries(self, url: str, params: dict) -> dict:
        return self._request_with_retries("GET", url, params)

    def _request_with_retries(self, method: str, url: str, params: dict) -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.request(method, url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = RETRY_BACKOFF_SECONDS * attempt
                    logger.warning("Instagram API rate limited, retrying in %ds", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Instagram API request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
                time.sleep(RETRY_BACKOFF_SECONDS)

        raise InstagramAPIError(f"Instagram API request failed after {MAX_RETRIES} attempts: {last_error}")
