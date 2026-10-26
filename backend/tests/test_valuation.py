import pytest

from app.models.league import LeagueSettings, Position, ScoringSettings
from app.services.valuation import build_valuation
from tests.conftest import build_pool, make_player


def test_replacement_levels_follow_league_starter_demand(league):
    val = build_valuation(build_pool(), league)
    assert val.starter_demand == {Position.QB: 4, Position.RB: 10, Position.WR: 10, Position.TE: 4}
    assert val.replacement_points == {
        Position.QB: 200.0, Position.RB: 100.0, Position.WR: 100.0, Position.TE: 100.0
    }


def test_value_over_replacement_is_never_negative(league):
    val = build_valuation(build_pool(), league)
    assert val.values["RB1"].value_over_replacement == 100.0  # 200 - 100
    assert val.values["RB16"].value_over_replacement == 0.0   # 50 pts, below replacement
    assert all(v.value_over_replacement >= 0 for v in val.values.values())


def test_positional_scarcity_beats_raw_points(league):
    # QB4 scores more raw points than RB5 but is barely above the deep QB replacement level.
    val = build_valuation(build_pool(), league)
    qb, rb = val.values["QB4"], val.values["RB5"]
    assert qb.projected_ros_points > rb.projected_ros_points
    assert rb.value_over_replacement > qb.value_over_replacement


def test_more_teams_raise_the_bar_for_replacement():
    small = build_valuation(build_pool(), LeagueSettings(num_teams=4))
    large = build_valuation(build_pool(), LeagueSettings(num_teams=6))
    assert large.replacement_points[Position.RB] < small.replacement_points[Position.RB]


@pytest.mark.parametrize("fmt, expected_ppg", [("ppr", 16.0), ("half_ppr", 13.0), ("standard", 10.0)])
def test_scoring_formats_change_player_points(fmt, expected_ppg):
    val = build_valuation(build_pool(), LeagueSettings(num_teams=4, scoring_format=fmt))
    assert val.values["WR_PPR"].projected_ppg == pytest.approx(expected_ppg)


def test_custom_scoring_te_premium():
    te = make_player("TE_X", "TE", 8, receptions=5)
    league = LeagueSettings(
        num_teams=4,
        scoring_format="custom",
        scoring=ScoringSettings(reception=1.0, te_reception_bonus=0.5),
    )
    val = build_valuation([*build_pool(), te], league)
    assert val.values["TE_X"].projected_ppg == pytest.approx(8 + 5 * 1.5)


def test_custom_format_requires_scoring():
    with pytest.raises(ValueError):
        LeagueSettings(scoring_format="custom")


def test_missing_projection_is_flagged_not_invented(league):
    val = build_valuation(build_pool(), league)
    v = val.values["RB_NOPROJ"]
    assert v.projection_available is False
    assert v.projected_ppg is None
    assert v.projected_ros_points == 0
    assert v.positional_rank is None


def test_games_remaining_scales_rest_of_season_value(league):
    val = build_valuation(build_pool(), league)
    assert val.values["WR_HURT"].projected_ppg == 15
    assert val.values["WR_HURT"].projected_ros_points == 60  # only 4 games left
