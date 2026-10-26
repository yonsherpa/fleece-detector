"""ESPN import: parsing, settings conversion, player matching, failures, and league-aware Moves.

All offline: ESPN responses are hand-built in the shape ESPN returns (see app/integrations/espn.py).
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations import espn
from app.integrations.espn import EspnError
from app.main import create_app
from app.models.league import SCORING_PRESETS, LeagueSettings
from app.models.moves import LeagueTeamRoster, MovesRequest
from app.models.player import Player, PlayerProjection
from app.services.errors import TradeValidationError
from app.services.league_import import EspnLeagueService, convert_scoring, scoring_format_for
from app.services.moves import build_moves
from app.services.player_matching import PlayerMatcher, normalize_name
from app.services.player_repository import PlayerRepository
from app.services.trending import TrendingService
from tests.conftest import TEST_DATASET, build_pool

DATASET_2026 = TEST_DATASET.model_copy(update={"season": 2026})


def real_player(pid: str, name: str, pos: str, ppg: float, espn_id: int | None = None) -> Player:
    field, per = {"QB": ("pass_yds", 0.04), "RB": ("rush_yds", 0.1)}.get(pos, ("rec_yds", 0.1))
    return Player(
        player_id=pid, name=name, position=pos, nfl_team="TST", games_remaining=10,
        projection=PlayerProjection(**{field: ppg / per}), espn_id=espn_id,
    )


@pytest.fixture
def named_repo() -> PlayerRepository:
    extra = [
        real_player("sleeper-1", "Josh Allen", "QB", 25, espn_id=3918298),
        real_player("sleeper-2", "D.J. Moore", "WR", 14),
        real_player("sleeper-3", "Kenneth Walker III", "RB", 18),
        real_player("sleeper-4", "Mike Williams", "WR", 9),
        real_player("sleeper-5", "Mike Williams", "WR", 8),  # same name, same position: ambiguous
        real_player("sleeper-6", "Amon-Ra St. Brown", "WR", 19),
    ]
    return PlayerRepository([*build_pool(), *extra], DATASET_2026)


def entry(pid, name, pos_id, slot, team=1):
    return {
        "lineupSlotId": slot,
        "playerPoolEntry": {"player": {"id": pid, "fullName": name, "defaultPositionId": pos_id, "proTeamId": team}},
    }


SCORING_ITEMS = [
    {"statId": 3, "points": 0.04}, {"statId": 4, "points": 4}, {"statId": 20, "points": -2},
    {"statId": 24, "points": 0.1}, {"statId": 25, "points": 6}, {"statId": 42, "points": 0.1},
    {"statId": 43, "points": 6}, {"statId": 72, "points": -2},
    {"statId": 19, "points": 2}, {"statId": 26, "points": 2}, {"statId": 44, "points": 2},
    {"statId": 53, "points": 0.5, "pointsOverrides": {"6": 1.0}},  # half PPR + TE premium
    {"statId": 45, "points": 2},  # 40+ yard TD bonus: not modeled
    {"statId": 80, "points": 3},  # a kicking stat: ignored, not reported
]

LEAGUE_JSON = {
    "seasonId": 2026,
    "scoringPeriodId": 7,
    "settings": {
        "name": "Dynasty Bros",
        "size": 4,
        "rosterSettings": {
            "lineupSlotCounts": {"0": 1, "2": 2, "4": 2, "6": 1, "23": 1, "16": 1, "17": 1, "20": 6, "21": 1}
        },
        "scoringSettings": {"scoringItems": SCORING_ITEMS},
    },
    "teams": [
        {
            "id": 1, "name": "Alpha", "abbrev": "ALP",
            "roster": {"entries": [
                entry(3918298, "Josh Allen", 1, 0),           # matched by ESPN id
                entry(111, "DJ Moore", 3, 4),                  # name match ("D.J." vs "DJ")
                entry(112, "Kenneth Walker", 2, 2),            # name match despite "III"
                entry(113, "Mike Williams", 3, 20),            # ambiguous: unmatched
                entry(114, "Some Kicker", 5, 17),              # kicker: unsupported
                entry(115, "Amon-Ra St. Brown", 3, 21),        # matched but on IR
            ]},
        },
        {
            "id": 2, "location": "Bravo", "nickname": "Bunch", "abbrev": "BRV",
            "roster": {"entries": [entry(201, "Test RB1", 2, 2), entry(202, "Test WR1", 3, 4)]},
        },
    ],
}


def service(data=LEAGUE_JSON, calls=None) -> EspnLeagueService:
    def fetcher(league_id, season):
        if calls is not None:
            calls.append((league_id, season))
        return data

    return EspnLeagueService(fetcher=fetcher)


# ---------- player matching ----------

@pytest.mark.parametrize(
    "raw, normalized",
    [("D.J. Moore", "dj moore"), ("Kenneth Walker III", "kenneth walker"), ("Amon-Ra St. Brown", "amon ra st brown"),
     ("Marvin Harrison Jr.", "marvin harrison"), ("José Núñez", "jose nunez")],
)
def test_normalize_name(raw, normalized):
    assert normalize_name(raw) == normalized


def test_matcher_strategies(named_repo):
    m = PlayerMatcher(named_repo.all_players())
    assert m.match(3918298, "J. Allen", "QB") == ("sleeper-1", "espn_id")
    assert m.match(None, "DJ Moore", "WR") == ("sleeper-2", "name_position")
    assert m.match(None, "Mike Williams", "WR") == (None, None)  # two candidates: don't guess
    assert m.match(None, "Nobody Here", "RB") == (None, None)


# ---------- settings conversion ----------

def test_scoring_conversion_with_te_premium():
    scoring, unmodeled = convert_scoring(SCORING_ITEMS)
    assert scoring.reception == 0.5
    assert scoring.te_reception_bonus == 0.5
    assert scoring.pass_yd == 0.04 and scoring.two_pt_conversion == 2
    assert unmodeled == 1  # only the 40+ yard TD bonus; the kicking stat is ignored
    assert scoring_format_for(scoring) == "custom"


def test_scoring_matching_a_preset_uses_the_preset():
    items = [i for i in SCORING_ITEMS if i["statId"] not in (45, 80)]
    items = [({**i, "pointsOverrides": {}} if i["statId"] == 53 else i) for i in items]
    scoring, _ = convert_scoring(items)
    assert scoring == SCORING_PRESETS["half_ppr"]
    assert scoring_format_for(scoring) == "half_ppr"


def test_every_n_yards_becomes_points_per_yard():
    scoring, _ = convert_scoring([{"statId": 6, "points": 1}, {"statId": 28, "points": 1}])  # 1 pt / 10 yds
    assert scoring.pass_yd == 0.1 and scoring.rush_yd == 0.1


def test_full_import(named_repo):
    league = service().get(123, 2026, named_repo)
    assert league.name == "Dynasty Bros"
    assert league.current_week == 7
    assert league.league_settings.num_teams == 4
    lineup = league.league_settings.lineup
    assert (lineup.QB, lineup.RB, lineup.WR, lineup.TE, lineup.FLEX, lineup.BENCH) == (1, 2, 2, 1, 1, 6)
    assert league.league_settings.scoring_format == "custom"

    alpha, bravo = league.teams
    assert bravo.name == "Bravo Bunch"  # built from location + nickname
    assert alpha.player_ids == ["sleeper-1", "sleeper-2", "sleeper-3"]  # IR player left out
    by_name = {p.name: p for p in alpha.players}
    assert by_name["Amon-Ra St. Brown"].player_id == "sleeper-6"  # matched, just not used while on IR
    assert by_name["Mike Williams"].player_id is None
    assert league.unmatched == ["Mike Williams (WR)"]
    assert league.unsupported_count == 1
    assert any("Kicker and D/ST" in n for n in league.notes)
    assert any("IR" in n for n in league.notes)


def test_only_current_season(named_repo):
    with pytest.raises(TradeValidationError, match="2026"):
        service().get(123, 2025, named_repo)


def test_league_is_cached(named_repo):
    calls = []
    svc = service(calls=calls)
    svc.get(123, 2026, named_repo)
    svc.get(123, 2026, named_repo)
    assert calls == [(123, 2026)]


# ---------- ESPN HTTP failures (faked transport, no network) ----------

def fake_client(status: int, body: bytes = b"{}") -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body)))


@pytest.mark.parametrize(
    "status, code", [(404, "not_found"), (401, "private"), (403, "private"), (500, "unavailable")]
)
def test_http_errors_map_to_clear_codes(status, code):
    with pytest.raises(EspnError) as exc:
        espn.fetch_league_json(1, 2026, client=fake_client(status))
    assert exc.value.code == code


def test_private_league_message_never_asks_for_credentials():
    with pytest.raises(EspnError) as exc:
        espn.fetch_league_json(1, 2026, client=fake_client(401))
    assert "never asks for your ESPN password" in str(exc.value)


def test_unreadable_response_and_network_failure():
    with pytest.raises(EspnError) as exc:
        espn.fetch_league_json(1, 2026, client=fake_client(200, b"<html>not json"))
    assert exc.value.code == "invalid"

    def boom(request):
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(EspnError) as exc:
        espn.fetch_league_json(1, 2026, client=httpx.Client(transport=httpx.MockTransport(boom)))
    assert exc.value.code == "unavailable"


def test_parse_rejects_missing_fields():
    with pytest.raises(EspnError) as exc:
        espn.parse_league({"messages": ["?"]}, 1, 2026)
    assert exc.value.code == "invalid"


# ---------- endpoints ----------

def make_client(repo, svc):
    return TestClient(create_app(repository=repo, trending=TrendingService(fetcher=lambda k: []), espn=svc))


def test_league_endpoints(named_repo):
    with make_client(named_repo, service()) as c:
        res = c.get("/leagues/123")
        assert res.status_code == 200
        assert res.json()["name"] == "Dynasty Bros"
        teams = c.get("/leagues/123/teams").json()
        assert [t["name"] for t in teams] == ["Alpha", "Bravo Bunch"]


@pytest.mark.parametrize("code, status", [("private", 403), ("not_found", 404), ("unavailable", 502)])
def test_league_endpoint_errors(named_repo, code, status):
    def failing(league_id, season):
        raise EspnError(code, "nope")

    with make_client(named_repo, EspnLeagueService(fetcher=failing)) as c:
        res = c.get("/leagues/123")
    assert res.status_code == status
    assert res.json()["error"]["code"] == f"espn_{code}"


def test_custom_scoring_query(client):
    ppr = client.get("/players/WR_PPR", params={"num_teams": 4}).json()["projected_ppg"]
    custom = client.get(
        "/players/WR_PPR", params={"num_teams": 4, "scoring_format": "custom", "scoring": "reception:2"}
    ).json()["projected_ppg"]
    assert (ppr, custom) == (16.0, 22.0)  # 10 yardage points + 6 receptions x 1 or x 2
    assert client.get("/players", params={"scoring_format": "custom", "scoring": "bogus:1"}).status_code == 422


# ---------- Moves with real league rosters ----------

def test_moves_use_real_free_agents_and_owners(repo, league):
    mine = ["QB1", "RB1", "RB2", "RB3", "RB4", "WR9", "WR10", "TE2", "QB6", "RB12", "WR13", "TE6"]
    others = [LeagueTeamRoster(team_name="Bravo", player_ids=["WR2", "WR3", "TE1"])]
    req = MovesRequest(roster=mine, league=league, league_rosters=others)
    result = build_moves(req, repo, TrendingService(fetcher=lambda k: []))
    assert result.availability == "league"
    # Free agents: anyone not on Bravo or on my roster, so WR1 (unowned, value 100) shows up as a waiver add.
    waiver_ids = {s.player.player_id for s in result.waiver_targets}
    assert "WR1" in waiver_ids and not waiver_ids & {"WR2", "WR3", "TE1"}
    assert all("Free agent in your league" in s.reason for s in result.waiver_targets)
    # Buy targets only come from players another team owns, and say who.
    assert result.buy_targets
    assert all(s.owner_team == "Bravo" for s in result.buy_targets)
    assert result.buy_targets[0].player.player_id == "WR2"
