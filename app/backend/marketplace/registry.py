"""Channel registry — the one place new marketplaces are wired in (spec §26)."""
from __future__ import annotations

from marketplace.amazon_spapi import AmazonSPAPIAdapter
from marketplace.base import MarketplaceAdapter
from marketplace.ondc import ONDCAdapter

_ADAPTERS: dict[str, MarketplaceAdapter] = {
    "amazon": AmazonSPAPIAdapter(),
    "ondc": ONDCAdapter(),
}


def get_adapter(channel: str) -> MarketplaceAdapter | None:
    return _ADAPTERS.get(channel)


def available_channels() -> list[str]:
    return list(_ADAPTERS.keys())


def channel_statuses() -> dict[str, bool]:
    """channel -> whether it is configured for real publishing."""
    return {name: adapter.enabled for name, adapter in _ADAPTERS.items()}
