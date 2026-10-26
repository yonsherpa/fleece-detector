from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.config import SNAPSHOT_DIR, Settings
from app.data.ingest.build import bye_weeks, build_players, remaining_weeks
from app.data.projection_provider import CsvProjectionProvider, DataSourceError
from app.models.league import SCORING_PRESETS
from app.models.player import DatasetInfo, Player, PlayerProjection
from app.models.trade import TradeRequest
from app.services.player_repository import create_repository
from app.services.scoring import fantasy_points_per_game
from app.services.trade_evaluator import _warnings, evaluate_trade

# ---------- transform (no network) ----------

# Week 7-9 slice of a season. TST played week 7 already; LA's week 8 is a bye.
SCHEDULE = pd.DataFrame(
    [
        (2026, "REG", 6, "TST", "LA", 3.0),
        (2026, "REG", 7, "TST", "OPP", 7.0),
        (2026, "REG", 7, "LA", "OPP2", None),
        (2026, "REG", 8, "OPP", "TST", None),
        (2026, "REG", 9, "LA", "TST", None),
    ],
    columns=["season", "game_type", "week", "home_team", "away_team", "result"],
)

PLAYERS = {
    "1": {"full_name": "Rams Receiver", "position": "WR", "team": "LAR", "active": True, "espn_id": 42,
          "injury_status": "Questionable"},
    "2": {"full_name": "Test Back", "position": "RB", "team": "TST", "active": True},
    "3": {"full_name": "Unprojected Guy", "position": "TE", "team": "TST", "active": True},
    "4": {"full_name": "Some Kicker", "position": "K", "team": "TST", "active": True},
}

WEEKLY = {
    7: {"1": {"pts_ppr": 15.0, "rec": 5, "rec_yd": 80, "rec_td": 0.5, "rec_2pt": 0.1}},
    8: {"2": {"pts_ppr": 12.0, "rush_yd": 90, "rush_td": 0.5}},
    9: {
        "1": {"pts_ppr": 9.0, "rec": 3, "rec_yd": 50, "rec_td": 0.2},
        "2": {"pts_ppr": 0.0},  # projected out this week: counts as a game worth 0
    },
}


def test_remaining_weeks_skips_completed_games():
    weeks = remaining_weeks(SCHEDULE, 2026, current_week=7)
    assert weeks["TST"] == [8, 9]  # week 7 already has a result
    assert weeks["LA"] == [7, 9]


def test_bye_week_is_the_week_a_team_does_not_play():
    assert bye_weeks(SCHEDULE, 2026)["LA"] == 8


def test_build_players_sums_projections_over_remaining_games():
    df = build_players(PLAYERS, WEEKLY, SCHEDULE, 2026, current_week=7).set_index("name")
    assert list(df.index) == ["Rams Receiver", "Test Back"]  # no projection / non-skill players dropped

    wr = df.loc["Rams Receiver"]
    assert wr.nfl_team == "LAR"  # Sleeper code kept for display, mapped to "LA" for the schedule
    assert wr.games_remaining == 2
    assert wr.receptions == 4.0  # (5 + 3) / 2 games
    assert wr.rec_yds == 65.0
    assert wr.two_pt_conversions == 0.05
    assert wr.injury_status == "QUESTIONABLE"
    assert wr.espn_id == 42

    rb = df.loc["Test Back"]
    assert rb.games_remaining == 2
    assert rb.rush_yds == 45.0  # 90 in week 8, projected 0 in week 9


def test_two_way_players_use_their_fantasy_position():
    # Travis Hunter is listed as "DB" but is fantasy-eligible (and projected) at WR.
    players = {"9": {"full_name": "Two Way", "position": "DB", "fantasy_positions": ["DB", "WR"], "team": "TST", "active": True}}
    weekly = {8: {"9": {"pts_ppr": 4.0, "rec": 1.5, "rec_yd": 20}}}
    df = build_players(players, weekly, SCHEDULE, 2026, current_week=7)
    assert df.loc[0, "position"] == "WR"
    assert df.loc[0, "player_id"] == "sleeper-9"


def test_our_scoring_reproduces_sleeper_ppr_points():
    # A real Sleeper week-9 projected stat line and its published pts_ppr (23.36).
    # Sleeper's default scoring is -1 per interception (ESPN's, our default, is -2).
    line = PlayerProjection(
        pass_yds=262.81, pass_tds=2.39, pass_ints=0.59, rush_yds=24.12, rush_tds=0.25,
        fumbles_lost=0.17, two_pt_conversions=0.14,
    )
    qb = Player(player_id="x", name="QB", position="QB", nfl_team="SF", games_remaining=1, projection=line)
    sleeper_rules = SCORING_PRESETS["ppr"].model_copy(update={"pass_int": -1.0})
    assert fantasy_points_per_game(qb, sleeper_rules) == pytest.approx(23.36, abs=0.05)


# ---------- snapshot + loading ----------

def test_real_snapshot_loads():
    players, dataset = CsvProjectionProvider(SNAPSHOT_DIR / "players.csv", SNAPSHOT_DIR / "metadata.json").load()
    assert dataset.is_sample is False
    assert dataset.source == "sleeper+nflverse"
    assert datetime.fromisoformat(dataset.as_of)
    assert len(players) >= 200
    assert {p.position.value for p in players} == {"QB", "RB", "WR", "TE"}
    assert all(p.player_id.startswith("sleeper-") for p in players)


def test_trade_on_real_snapshot_evaluates():
    repo = create_repository(Settings(cors_origins=[], data_source="snapshot"))
    some = sorted(repo.search(TradeRequest.model_fields["league"].default_factory())[0], key=lambda v: v.player_id)
    result = evaluate_trade(TradeRequest(team_a_gives=[some[0].player_id], team_a_receives=[some[1].player_id]), repo)
    assert result.grade
    assert not any("SYNTHETIC" in w for w in result.warnings)


def test_unavailable_source_falls_back_to_snapshot(tmp_path: Path):
    repo = create_repository(Settings(cors_origins=[], data_source=str(tmp_path / "missing.csv")))
    assert repo.dataset.source == "sleeper+nflverse"


def test_stale_data_produces_warning():
    dataset = DatasetInfo(source="x", is_sample=False, as_of="2026-10-01T00:00:00+00:00", week=4, description="")
    fresh = _warnings([], dataset, now=datetime(2026, 10, 2, tzinfo=timezone.utc))
    stale = _warnings([], dataset, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert fresh == []
    assert any("19 days ago" in w for w in stale)


# ---------- CSV validation ----------

def test_csv_missing_columns_raises(tmp_path: Path):
    bad = tmp_path / "bad.csv"
    bad.write_text("player_id,name\nX,Someone\n", encoding="utf-8")
    with pytest.raises(DataSourceError, match="missing columns"):
        CsvProjectionProvider(bad).load()


def test_csv_duplicate_ids_raise(tmp_path: Path):
    dup = tmp_path / "dup.csv"
    dup.write_text(
        "player_id,name,position,nfl_team,games_remaining\nX,A,RB,KC,9\nX,B,WR,KC,9\n", encoding="utf-8"
    )
    with pytest.raises(DataSourceError, match="Duplicate"):
        CsvProjectionProvider(dup).load()


def test_csv_without_metadata_reports_unknown_timestamp(tmp_path: Path):
    csv = tmp_path / "p.csv"
    csv.write_text(
        "player_id,name,position,nfl_team,games_remaining,rush_yds\nX,A,RB,KC,9,80\n", encoding="utf-8"
    )
    players, dataset = CsvProjectionProvider(csv).load()
    assert dataset.as_of == "unknown"
    assert players[0].projection.rush_yds == 80
