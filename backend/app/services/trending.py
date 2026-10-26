"""Live "trending" adds/drops from Sleeper, cached in memory.

Unlike projections (a saved snapshot), trends are only meaningful when fresh, so
they're fetched at request time. A short cache keeps us far below Sleeper's
rate limit, and any failure degrades to "trending unavailable" instead of an error.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx

from app.data.ingest import sources
from app.data.projection_provider import DataSourceError

logger = logging.getLogger(__name__)

LOOKBACK_HOURS = 24
LIMIT = 25
CACHE_SECONDS = 30 * 60


@dataclass
class TrendingSnapshot:
    adds: list[dict] = field(default_factory=list)  # [{"player_id": "sleeper id", "count": int}]
    drops: list[dict] = field(default_factory=list)
    fetched_at: str | None = None
    error: str | None = None


Fetcher = Callable[[str], list[dict]]


def _sleeper_fetcher(kind: str) -> list[dict]:
    with httpx.Client(timeout=httpx.Timeout(8.0), headers={"User-Agent": "fleece-detector/0.1"}) as client:
        return sources.fetch_trending(client, kind, LOOKBACK_HOURS, LIMIT)


class TrendingService:
    def __init__(self, fetcher: Fetcher = _sleeper_fetcher, ttl_seconds: float = CACHE_SECONDS) -> None:
        self._fetcher = fetcher
        self._ttl = ttl_seconds
        self._cached: TrendingSnapshot | None = None
        self._cached_at = 0.0

    def get(self) -> TrendingSnapshot:
        if self._cached and self._cached.error is None and time.monotonic() - self._cached_at < self._ttl:
            return self._cached
        try:
            snapshot = TrendingSnapshot(
                adds=self._fetcher("add"),
                drops=self._fetcher("drop"),
                fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            )
        except (DataSourceError, httpx.HTTPError, ValueError) as exc:
            logger.warning("Trending fetch failed: %s", exc)
            # Keep serving the last good data if we have it; otherwise report the outage.
            if self._cached and self._cached.error is None:
                return self._cached
            return TrendingSnapshot(error="Sleeper's trending data couldn't be reached right now.")
        self._cached, self._cached_at = snapshot, time.monotonic()
        return snapshot
