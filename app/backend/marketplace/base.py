"""
Marketplace adapter interface (spec §12, §14, §26).

Every channel implements the same contract so the core product pipeline never
needs to know channel specifics. A publish returns a PublishResult; the
orchestrator maps it onto the ProductChannel row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class PublishResult:
    ok: bool
    external_product_id: str | None = None
    listing_url: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class MarketplaceAdapter(Protocol):
    name: str

    @property
    def enabled(self) -> bool:
        """Whether credentials/config are present for real calls."""
        ...

    def publish(self, product: dict[str, Any]) -> PublishResult:
        """Create/update a listing from a canonical product dict."""
        ...
