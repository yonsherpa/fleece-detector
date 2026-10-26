"""Network fetchers for the public data sources. Each raises DataSourceError on failure.

* Sleeper API (https://docs.sleeper.com): free, read-only, no authentication.
  Their guidance is to stay under 1000 calls/minute; a full refresh makes ~14 calls.
* nflverse schedule data (https://github.com/nflverse/nfldata).
"""

from __future__ import annotations

import io
from typing import Any

import httpx
import pandas as pd

from app.data.projection_provider import DataSourceError

SLEEPER = "https://api.sleeper.app/v1"
NFLVERSE_SCHEDULE = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
TIMEOUT = httpx.Timeout(60.0)


def _get(client: httpx.Client, url: str) -> httpx.Response:
    try:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise DataSourceError(f"Request to {url} failed: {exc}") from exc


def fetch_state(client: httpx.Client) -> dict[str, Any]:
    """Current season and week, e.g. {"season": "2026", "week": 7, ...}."""
    return _get(client, f"{SLEEPER}/state/nfl").json()


def fetch_players(client: httpx.Client) -> dict[str, dict[str, Any]]:
    """Every NFL player Sleeper knows about (~15 MB), keyed by Sleeper player id."""
    return _get(client, f"{SLEEPER}/players/nfl").json()


def fetch_week_projections(client: httpx.Client, season: int, week: int) -> dict[str, dict[str, Any]]:
    return _get(client, f"{SLEEPER}/projections/nfl/regular/{season}/{week}").json()


def fetch_trending(client: httpx.Client, kind: str, lookback_hours: int, limit: int) -> list[dict[str, Any]]:
    """Most added ("add") or dropped ("drop") players across Sleeper leagues: [{"player_id", "count"}]."""
    url = f"{SLEEPER}/players/nfl/trending/{kind}?lookback_hours={lookback_hours}&limit={limit}"
    return _get(client, url).json()


def fetch_schedule(client: httpx.Client) -> pd.DataFrame:
    text = _get(client, NFLVERSE_SCHEDULE).text
    return pd.read_csv(io.StringIO(text), usecols=["season", "game_type", "week", "home_team", "away_team", "result"])
