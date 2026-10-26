"""Refresh the player snapshot from Sleeper + nflverse.

Run from backend/:  python scripts/update_data.py

Writes app/data/snapshot/players.csv and metadata.json. The new files only replace
the old ones after every fetch and sanity check succeeds, so a failed refresh
leaves the last good snapshot in place and the app keeps working.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import SNAPSHOT_DIR  # noqa: E402
from app.data.ingest import sources  # noqa: E402
from app.data.ingest.build import SKILL_POSITIONS, build_players  # noqa: E402
from app.data.projection_provider import DataSourceError  # noqa: E402

LAST_REGULAR_SEASON_WEEK = 18
MIN_PLAYERS = 200


def main() -> int:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        with httpx.Client(timeout=sources.TIMEOUT, headers={"User-Agent": "fleece-detector/0.1"}) as client:
            state = sources.fetch_state(client)
            season, week = int(state["season"]), int(state["week"])
            print(f"Season {season}, week {week}. Fetching players...")
            players = sources.fetch_players(client)
            print("Fetching weekly projections...")
            weekly = {
                w: sources.fetch_week_projections(client, season, w)
                for w in range(week, LAST_REGULAR_SEASON_WEEK + 1)
            }
            print("Fetching schedule...")
            schedule = sources.fetch_schedule(client)
    except (DataSourceError, KeyError, ValueError) as exc:
        print(f"Refresh failed, keeping the existing snapshot: {exc}", file=sys.stderr)
        return 1

    df = build_players(players, weekly, schedule, season, week)

    counts = df["position"].value_counts().to_dict()
    if len(df) < MIN_PLAYERS or any(counts.get(pos, 0) == 0 for pos in SKILL_POSITIONS):
        print(f"Refresh produced suspicious data ({counts}); keeping the existing snapshot.", file=sys.stderr)
        return 1

    metadata = {
        "source": "sleeper+nflverse",
        "is_sample": False,
        "as_of": fetched_at,
        "season": season,
        "week": week,
        "description": (
            f"Real NFL players. Rest-of-season projections are Sleeper's weekly projections summed over "
            f"each team's remaining games (weeks {week}-{LAST_REGULAR_SEASON_WEEK}); schedule and bye weeks "
            f"from nflverse."
        ),
    }

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_csv, tmp_meta = SNAPSHOT_DIR / "players.csv.tmp", SNAPSHOT_DIR / "metadata.json.tmp"
    df.to_csv(tmp_csv, index=False)
    tmp_meta.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    tmp_csv.replace(SNAPSHOT_DIR / "players.csv")
    tmp_meta.replace(SNAPSHOT_DIR / "metadata.json")

    print(f"Wrote {len(df)} players {counts} to {SNAPSHOT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
