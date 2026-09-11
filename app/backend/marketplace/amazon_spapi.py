"""
Amazon Selling Partner API (SP-API) adapter — real integration structure.

Implements the two calls that matter for listing a product:

1. LWA token exchange  — POST https://api.amazon.com/auth/o2/token
   (grant_type=refresh_token) to mint a short-lived access token.
2. Listings Items API  — PUT /listings/2021-08-01/items/{sellerId}/{sku}
   to create/replace a listing.

Notes
-----
* SP-API dropped AWS SigV4 in favour of a plain bearer access token
  (Aug 2023+), so no AWS credentials are required here — only LWA.
* When AMAZON_SANDBOX=true the sandbox host is used; the same code path runs
  against production by flipping the flag and supplying real seller creds.
* If credentials are absent, ``enabled`` is False and the orchestrator marks
  the channel NEEDS_ATTENTION rather than calling the API — the artisan is
  told to complete Amazon seller authorization (spec §13 constraint).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from core.config import settings
from marketplace.base import PublishResult

logger = logging.getLogger(__name__)

# SP-API regional endpoints. India is served by the EU endpoint.
_ENDPOINTS = {
    "na": "https://sellingpartnerapi-na.amazon.com",
    "eu": "https://sellingpartnerapi-eu.amazon.com",
    "fe": "https://sellingpartnerapi-fe.amazon.com",
}
_SANDBOX = {
    "na": "https://sandbox.sellingpartnerapi-na.amazon.com",
    "eu": "https://sandbox.sellingpartnerapi-eu.amazon.com",
    "fe": "https://sandbox.sellingpartnerapi-fe.amazon.com",
}
_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


class AmazonSPAPIAdapter:
    name = "amazon"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(
            settings.amazon_enabled
            and settings.amazon_lwa_client_id
            and settings.amazon_lwa_client_secret
            and settings.amazon_refresh_token
            and settings.amazon_seller_id
        )

    @property
    def base_url(self) -> str:
        table = _SANDBOX if settings.amazon_sandbox else _ENDPOINTS
        return table.get(settings.amazon_region, table["eu"])

    # ── LWA ─────────────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        resp = httpx.post(
            _LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": settings.amazon_refresh_token,
                "client_id": settings.amazon_lwa_client_id,
                "client_secret": settings.amazon_lwa_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    # ── Mapping ─────────────────────────────────────────────────────────────

    @staticmethod
    def _sku(product: dict[str, Any]) -> str:
        return f"ART-{product['id'][:12].upper()}"

    def _to_listing_attributes(self, product: dict[str, Any]) -> dict[str, Any]:
        """Map the canonical product onto SP-API Listings attributes.

        The exact required attributes depend on the product type; this covers
        the common set. A real deployment resolves the productType via the
        Product Type Definitions API first.
        """
        marketplace_id = settings.amazon_marketplace_id
        price = product.get("price") or product.get("suggested_price") or 0
        bullets = [{"value": h, "marketplace_id": marketplace_id}
                   for h in (product.get("highlights") or [])[:5]]
        return {
            "condition_type": [{"value": "new_new", "marketplace_id": marketplace_id}],
            "item_name": [{"value": (product.get("title") or "")[:200],
                           "marketplace_id": marketplace_id}],
            "brand": [{"value": product.get("business_name") or "Handmade",
                       "marketplace_id": marketplace_id}],
            "product_description": [{"value": product.get("long_description") or "",
                                     "marketplace_id": marketplace_id}],
            "bullet_point": bullets,
            "list_price": [{"currency": product.get("currency", "INR"),
                            "value": float(price), "marketplace_id": marketplace_id}],
        }

    # ── Publish ─────────────────────────────────────────────────────────────

    def publish(self, product: dict[str, Any]) -> PublishResult:
        if not self.enabled:
            return PublishResult(
                ok=False,
                error="Amazon seller authorization incomplete. Connect your Amazon "
                      "seller account to enable automatic publishing.",
            )
        try:
            token = self._get_access_token()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Amazon LWA token exchange failed")
            return PublishResult(ok=False, error=f"Amazon authentication failed: {exc}")

        sku = self._sku(product)
        seller_id = settings.amazon_seller_id
        url = f"{self.base_url}/listings/2021-08-01/items/{seller_id}/{sku}"
        params = {
            "marketplaceIds": settings.amazon_marketplace_id,
            "issueLocale": "en_IN",
        }
        body = {
            # productType should ideally come from the Product Type Definitions
            # API; HOME is a safe generic default for many handicrafts.
            "productType": "HOME",
            "requirements": "LISTING",
            "attributes": self._to_listing_attributes(product),
        }
        try:
            resp = httpx.put(
                url,
                params=params,
                json=body,
                headers={
                    "x-amz-access-token": token,
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            return PublishResult(ok=False, error=f"Amazon network error: {exc}")

        if resp.status_code >= 400:
            return PublishResult(
                ok=False,
                error=self._extract_error(resp),
                raw=self._safe_json(resp),
            )

        data = self._safe_json(resp)
        status = data.get("status", "ACCEPTED")
        ok = status in ("ACCEPTED", "VALID")
        marketplace_domain = "amazon.in"
        listing_url = f"https://www.{marketplace_domain}/dp/{sku}" if ok else None
        return PublishResult(
            ok=ok,
            external_product_id=sku,
            listing_url=listing_url,
            error=None if ok else f"Amazon returned status {status}",
            raw=data,
        )

    @staticmethod
    def _safe_json(resp: httpx.Response) -> dict[str, Any]:
        try:
            return resp.json()
        except Exception:  # noqa: BLE001
            return {"body": resp.text[:500]}

    @staticmethod
    def _extract_error(resp: httpx.Response) -> str:
        try:
            data = resp.json()
            issues = data.get("issues") or data.get("errors") or []
            if issues:
                msgs = [i.get("message", "") for i in issues]
                return "; ".join(m for m in msgs if m)[:400] or f"HTTP {resp.status_code}"
        except Exception:  # noqa: BLE001
            pass
        return f"Amazon HTTP {resp.status_code}: {resp.text[:200]}"
