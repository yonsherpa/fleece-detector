"""Shared fixtures: a tiny, hand-calculable 4-team league.

Every fixture player plays 10 games and scores an exact number of points per game
(yardage only, so PPR/standard don't matter unless a test adds receptions).

Pools (ppg):  QB 24..17   RB 20..5   WR 20..5   TE 14..7
With 4 teams and QB/2RB/2WR/TE/FLEX, league-wide starters are QB 4, RB 10, WR 10,
TE 4, so replacement-level ROS points are QB 200, RB 100, WR 100, TE 100.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.league import LeagueSettings
from app.models.player import DatasetInfo, Player, PlayerProjection
from app.services.player_repository import PlayerRepository
from app.services.trending import TrendingService

YARD_FIELD = {"QB": ("pass_yds", 0.04), "RB": ("rush_yds", 0.1), "WR": ("rec_yds", 0.1), "TE": ("rec_yds", 0.1)}


def make_player(
    player_id: str,
    position: str,
    ppg: float | None,
    games: int = 10,
    receptions: float = 0.0,
    injury_status: str | None = None,
) -> Player:
    projection = None
    if ppg is not None:
        field, pts_per_yd = YARD_FIELD[position]
        projection = PlayerProjection(**{field: ppg / pts_per_yd, "receptions": receptions})
    return Player(
        player_id=player_id,
        name=f"Test {player_id}",
        position=position,
        nfl_team="TST",
        games_remaining=games,
        injury_status=injury_status,
        projection=projection,
    )


def build_pool() -> list[Player]:
    players = []
    for pos, count, top in [("QB", 8, 24), ("RB", 16, 20), ("WR", 16, 20), ("TE", 8, 14)]:
        for i in range(count):
            players.append(make_player(f"{pos}{i + 1}", pos, top - i))
    players.append(make_player("RB_NOPROJ", "RB", None))
    players.append(make_player("WR_PPR", "WR", 10, receptions=6))
    players.append(make_player("WR_HURT", "WR", 15, games=4, injury_status="OUT"))
    return players


TEST_DATASET = DatasetInfo(
    source="unit_test_fixture", is_sample=False, as_of="2026-01-01T00:00:00+00:00", description="test"
)


@pytest.fixture
def repo() -> PlayerRepository:
    return PlayerRepository(build_pool(), TEST_DATASET)


@pytest.fixture
def league() -> LeagueSettings:
    # Standard scoring keeps WR_PPR (receptions) out of the WR replacement calculation.
    return LeagueSettings(num_teams=4, scoring_format="standard")


@pytest.fixture
def client(repo: PlayerRepository):
    # A fake trending source keeps tests offline (the real one calls Sleeper's API).
    trending = TrendingService(fetcher=lambda kind: [])
    with TestClient(create_app(repository=repo, trending=trending)) as c:
        yield c
