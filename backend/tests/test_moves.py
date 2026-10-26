"""Moves suggestions on the hand-calculable fixture league (see conftest.py for the numbers).

Roster used below (4 teams, standard scoring, default lineup):
  starters: QB1 240 | RB1 200, RB2 190 | WR9 120, WR10 110 | TE2 130 | FLEX RB3 180  -> 1170
  bench:    RB4 170, QB6 190, RB12 90, WR13 80, TE6 90
"""

import pytest

from app.data.projection_provider import DataSourceError
from app.models.league import LeagueSettings, LineupSlots
from app.models.moves import MovesRequest
from app.services.errors import TradeValidationError
from app.services.moves import build_moves
from app.services.player_repository import PlayerRepository
from app.services.trending import TrendingService
from tests.conftest import TEST_DATASET, build_pool, make_player

ROSTER = ["QB1", "RB1", "RB2", "RB3", "RB4", "WR9", "WR10", "TE2", "QB6", "RB12", "WR13", "TE6"]


@pytest.fixture
def repo_with_trending_player() -> PlayerRepository:
    # A deep-bench WR with a Sleeper-style id, so trending data can match it. At 1 ppg it sits
    # at the bottom of the WR pool and doesn't move any replacement level.
    return PlayerRepository([*build_pool(), make_player("sleeper-901", "WR", 1)], TEST_DATASET)


def fake_trending(adds=None, drops=None) -> TrendingService:
    data = {"add": adds or [], "drop": drops or []}
    return TrendingService(fetcher=lambda kind: data[kind])


def moves(repo, league, roster=ROSTER, trending=None):
    return build_moves(MovesRequest(roster=roster, league=league), repo, trending or fake_trending())


def by_id(items):
    return {s.player.player_id: s for s in items}


def test_sell_high_finds_valuable_players_you_barely_use(repo, league):
    result = moves(repo, league)
    sell = by_id(result.sell_high)
    # RB4 (value 70) sits on the bench: trading them costs nothing.
    assert sell["RB4"].lineup_change == 0
    # RB3 (value 80) starts at FLEX, but RB4 would step in: cost 180 - 170 = 10, under 25% of 80.
    assert sell["RB3"].lineup_change == -10
    # Even RB2 (value 90) qualifies: RB3 and RB4 each move up a slot, so the lineup loses only
    # 190 - 170 = 20, under 25% of 90. Four good RBs means any one of the top-3's backups is surplus.
    assert sell["RB2"].lineup_change == -20
    # RB1 is the core of the lineup (cost 30 > 25% of 100); never a sell-high suggestion.
    assert "RB1" not in sell
    assert [s.player.player_id for s in result.sell_high] == ["RB2", "RB3", "RB4"]  # highest value first


def test_safe_to_drop_is_replacement_level_bench(repo, league):
    drop = by_id(moves(repo, league).safe_to_drop)
    assert set(drop) == {"QB6", "RB12", "WR13", "TE6"}
    assert all(s.player.value_over_replacement <= 1 and s.lineup_change == 0 for s in drop.values())


def test_buy_targets_respect_budget_and_rank_by_lineup_gain(repo, league):
    result = moves(repo, league)
    assert result.buy_budget == 90  # best sell-high piece (RB2)
    first = result.buy_targets[0]
    assert first.player.player_id == "WR2"  # 190 replaces WR10 (110): +80
    assert first.lineup_change == 80
    assert all(s.player.value_over_replacement <= 90 * 1.1 for s in result.buy_targets)
    gains = [s.lineup_change for s in result.buy_targets]
    assert gains == sorted(gains, reverse=True)
    assert "WR1" not in by_id(result.buy_targets)  # value 100: over budget (99)


def test_waiver_targets_are_ranked_below_the_rostered_cutoff(repo):
    small_bench = LeagueSettings(num_teams=4, scoring_format="standard", lineup=LineupSlots(BENCH=2))
    result = moves(repo, small_bench, roster=None)
    assert result.rostered_cutoff == 36  # 4 teams x 9 roster spots
    assert result.waiver_targets
    assert all("outside the ~36 players" in s.reason for s in result.waiver_targets)
    ros = [s.player.projected_ros_points for s in result.waiver_targets]
    assert ros == sorted(ros, reverse=True)


def test_without_roster_personal_sections_are_empty_and_explained(repo, league):
    result = moves(repo, league, roster=None)
    assert not result.has_roster
    assert result.sell_high == result.safe_to_drop == result.buy_targets == []
    assert any("Add your roster" in n for n in result.notes)


def test_trending_matches_dataset_and_reports_gain(repo_with_trending_player, league):
    trending = fake_trending(
        adds=[{"player_id": "901", "count": 5000}, {"player_id": "999", "count": 10}],
        drops=[{"player_id": "901", "count": 40}],
    )
    result = moves(repo_with_trending_player, league, trending=trending)
    assert result.trending.available
    assert result.trending.unprojected_count == 1  # "999" isn't in the projections
    add = result.trending_adds[0]
    assert add.player.player_id == "sleeper-901"
    assert add.trend_count == 5000
    assert add.lineup_change == 0  # a 1 ppg WR can't crack this lineup
    assert result.trending_drops[0].trend_count == 40


def test_trending_outage_degrades_gracefully(repo, league):
    def broken(kind):
        raise DataSourceError("Sleeper is down")

    result = moves(repo, league, trending=TrendingService(fetcher=broken))
    assert not result.trending.available
    assert "couldn't be reached" in result.trending.message
    assert result.trending_adds == []
    assert result.sell_high  # everything else still works


def test_trending_is_cached():
    calls = []
    service = TrendingService(fetcher=lambda kind: calls.append(kind) or [])
    service.get()
    service.get()
    assert calls == ["add", "drop"]  # second call served from cache


def test_oversized_roster_rejected(repo, league):
    big = ROSTER + ["RB13", "WR14", "TE7"]  # 15 > 14
    with pytest.raises(TradeValidationError, match="maximum"):
        moves(repo, league, roster=big)


def test_moves_endpoint(client):
    res = client.post("/moves", json={"roster": ROSTER, "league": {"num_teams": 4, "scoring_format": "standard"}})
    assert res.status_code == 200
    body = res.json()
    assert body["has_roster"] is True
    assert {s["player"]["player_id"] for s in body["sell_high"]} == {"RB2", "RB3", "RB4"}
    assert body["trending"]["available"] is True  # the client fixture's fake source returns empty lists
