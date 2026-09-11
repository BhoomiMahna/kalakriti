"""Simple, thread-safe, append-only JSONL persistence for scores + engagement."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class FeedbackStore:
    """
    Append-only JSONL file. Each line is one record:

        {
          "product_id": "...",
          "category": "...",
          "instagram_post_id": "...",
          "worthiness_score": 0.82,
          "engagement": {"likes": 12, "comments": 3, ..., "reach": 400},
          "published_at": "2026-09-06T10:00:00",
          "recorded_at": "2026-09-06T22:00:00"
        }

    Good enough for the volumes this pipeline expects (dozens-hundreds of
    posts). Swap for SQLite later if you need concurrent multi-process
    writers or richer queries -- the public method signatures here won't
    need to change.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self.path.touch()

    def append(self, record: dict) -> None:
        record = dict(record)
        record.setdefault("recorded_at", datetime.utcnow().isoformat())
        line = json.dumps(record, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def get_category_stats(self, category: str) -> dict:
        records = [
            r
            for r in self._read_all()
            if r.get("category") == category and r.get("engagement")
        ]
        if not records:
            return {"post_count": 0, "avg_engagement_rate": 0.0}

        rates = []
        for r in records:
            eng = r["engagement"]
            reach = eng.get("reach", 0)
            if reach <= 0:
                continue
            interactions = (
                eng.get("likes", 0)
                + eng.get("comments", 0)
                + eng.get("shares", 0)
                + eng.get("saves", 0)
            )
            rates.append(interactions / reach)

        avg_rate = sum(rates) / len(rates) if rates else 0.0
        return {"post_count": len(records), "avg_engagement_rate": round(avg_rate, 4)}

    def get_hourly_engagement(self) -> dict[int, float]:
        """Average engagement rate bucketed by publish hour-of-day (0-23)."""
        records = [r for r in self._read_all() if r.get("engagement") and r.get("published_at")]
        buckets: dict[int, list[float]] = {}
        for r in records:
            try:
                hour = datetime.fromisoformat(r["published_at"]).hour
            except (ValueError, TypeError):
                continue
            eng = r["engagement"]
            reach = eng.get("reach", 0)
            if reach <= 0:
                continue
            interactions = (
                eng.get("likes", 0)
                + eng.get("comments", 0)
                + eng.get("shares", 0)
                + eng.get("saves", 0)
            )
            buckets.setdefault(hour, []).append(interactions / reach)

        return {h: round(sum(v) / len(v), 4) for h, v in buckets.items()}

    def get_recent_posts(self, days: int = 30) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        results = []
        for r in self._read_all():
            ts = r.get("published_at") or r.get("recorded_at")
            try:
                if ts and datetime.fromisoformat(ts) >= cutoff:
                    results.append(r)
            except (ValueError, TypeError):
                continue
        return results

    def last_published_at(self) -> Optional[datetime]:
        """Most recent publish timestamp across all posts (for spacing checks)."""
        times = []
        for r in self._read_all():
            ts = r.get("published_at")
            if not ts:
                continue
            try:
                times.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                continue
        return max(times) if times else None
