"""ESPN fantasy football league reader (public leagues only).

ESPN has no official public API. Its website reads league data from
`lm-api-reads.fantasy.espn.com`, which serves *public* leagues without a login.
Private leagues answer 401 unless the request carries the owner's ESPN session
cookies; we deliberately never ask for or store those, so private leagues get a
clear "make it viewable" message instead.

Code tables below come from ESPN's responses as documented by the open-source
espn-api project (github.com/cwendt94/espn-api). This module only fetches and
parses; turning a league into Fleece Detector settings lives in
app/services/league_import.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import httpx

ESPN_LEAGUE_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{league_id}"
VIEWS = ["mSettings", "mTeam", "mRoster"]

# Player `defaultPositionId` -> position.
PLAYER_POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}

# Lineup slot ids.
SLOT_QB, SLOT_RB, SLOT_RB_WR, SLOT_WR, SLOT_WR_TE, SLOT_TE, SLOT_OP = 0, 2, 3, 4, 5, 6, 7
SLOT_DST, SLOT_K, SLOT_BENCH, SLOT_IR, SLOT_FLEX = 16, 17, 20, 21, 23
SLOT_NAMES = {
    SLOT_QB: "QB", SLOT_RB: "RB", SLOT_RB_WR: "RB/WR", SLOT_WR: "WR", SLOT_WR_TE: "WR/TE", SLOT_TE: "TE",
    SLOT_OP: "SUPERFLEX", SLOT_DST: "D/ST", SLOT_K: "K", SLOT_BENCH: "BENCH", SLOT_IR: "IR", SLOT_FLEX: "FLEX",
}

# proTeamId -> abbreviation, converted to the codes our (Sleeper) data uses.
PRO_TEAMS = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GB", 10: "TEN",
    11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG",
    20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB",
    28: "WAS",  # ESPN says "WSH"; Sleeper says "WAS"
    29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}

ErrorCode = Literal["not_found", "private", "unavailable", "invalid"]


class EspnError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class EspnPlayer:
    espn_id: int
    name: str
    position: str  # QB/RB/WR/TE/K/DST or "OTHER"
    nfl_team: str | None
    injury_status: str | None
    lineup_slot: str


@dataclass
class EspnTeam:
    team_id: int
    name: str
    abbrev: str
    players: list[EspnPlayer] = field(default_factory=list)


@dataclass
class EspnLeague:
    league_id: int
    season: int
    name: str
    size: int
    current_week: int | None
    lineup_slot_counts: dict[int, int]
    scoring_items: list[dict[str, Any]]
    teams: list[EspnTeam]


Fetcher = Callable[[int, int], dict[str, Any]]


def fetch_league_json(league_id: int, season: int, client: httpx.Client | None = None) -> dict[str, Any]:
    """GET the league from ESPN. Raises EspnError with a user-facing message on any failure.

    `client` is injectable so tests can fake ESPN's responses without network access.
    """
    url = ESPN_LEAGUE_URL.format(season=season, league_id=league_id)
    own_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(12.0), headers={"User-Agent": "fleece-detector/0.1"})
    try:
        response = client.get(url, params=[("view", v) for v in VIEWS])
    except httpx.HTTPError as exc:
        raise EspnError("unavailable", "ESPN couldn't be reached. Try again in a minute.") from exc
    finally:
        if own_client:
            client.close()

    if response.status_code == 404:
        raise EspnError("not_found", f"No ESPN league {league_id} exists for the {season} season.")
    if response.status_code in (401, 403):
        raise EspnError(
            "private",
            "This league is private. ESPN only shares public leagues without a login, and Fleece Detector "
            "never asks for your ESPN password or cookies. A league manager can make the league viewable "
            "to the public in ESPN's league settings, or you can enter your roster by hand.",
        )
    if response.status_code >= 400:
        raise EspnError("unavailable", f"ESPN returned an error ({response.status_code}). Try again later.")
    try:
        return response.json()
    except ValueError as exc:
        raise EspnError("invalid", "ESPN sent a response we couldn't read.") from exc


def _team_name(team: dict[str, Any]) -> str:
    if team.get("name"):
        return str(team["name"]).strip()
    joined = f"{team.get('location', '')} {team.get('nickname', '')}".strip()
    return joined or f"Team {team.get('id')}"


def parse_league(data: dict[str, Any], league_id: int, season: int) -> EspnLeague:
    """Turn ESPN's JSON into plain dataclasses. Raises EspnError("invalid") if key fields are missing."""
    try:
        settings = data["settings"]
        teams_raw = data["teams"]
    except (KeyError, TypeError) as exc:
        raise EspnError("invalid", "ESPN's response is missing league settings or teams.") from exc

    teams = []
    for t in teams_raw:
        players = []
        for entry in (t.get("roster") or {}).get("entries", []):
            p = (entry.get("playerPoolEntry") or {}).get("player") or {}
            if "id" not in p:
                continue
            players.append(
                EspnPlayer(
                    espn_id=int(p["id"]),
                    name=str(p.get("fullName", "")).strip(),
                    position=PLAYER_POSITIONS.get(p.get("defaultPositionId"), "OTHER"),
                    nfl_team=PRO_TEAMS.get(p.get("proTeamId")),
                    injury_status=p.get("injuryStatus"),
                    lineup_slot=SLOT_NAMES.get(entry.get("lineupSlotId"), "OTHER"),
                )
            )
        teams.append(
            EspnTeam(team_id=int(t["id"]), name=_team_name(t), abbrev=str(t.get("abbrev", "")), players=players)
        )

    slot_counts = {
        int(k): int(v) for k, v in ((settings.get("rosterSettings") or {}).get("lineupSlotCounts") or {}).items()
    }
    return EspnLeague(
        league_id=league_id,
        season=int(data.get("seasonId", season)),
        name=str(settings.get("name", f"ESPN league {league_id}")),
        size=int(settings.get("size", len(teams))),
        current_week=data.get("scoringPeriodId"),
        lineup_slot_counts=slot_counts,
        scoring_items=list((settings.get("scoringSettings") or {}).get("scoringItems", [])),
        teams=sorted(teams, key=lambda t: t.team_id),
    )
