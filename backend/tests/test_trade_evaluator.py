import pytest

from app.models.league import LeagueSettings, LineupSlots, Position
from app.models.trade import TradeRequest
from app.services.errors import TradeValidationError, UnknownPlayerError
from app.services.grading import letter_grade
from app.services.trade_evaluator import evaluate_trade


def trade(league, gives, receives, roster_a=None, roster_b=None) -> TradeRequest:
    return TradeRequest(
        team_a_gives=gives,
        team_a_receives=receives,
        team_a_roster=roster_a,
        team_b_roster=roster_b,
        league=league,
    )


# Rosters for roster-aware tests. A is RB-rich / WR-poor; B is the opposite.
ROSTER_A = ["QB1", "RB1", "RB2", "RB3", "WR9", "WR10", "TE2", "QB6", "RB12", "WR13", "TE6"]
ROSTER_B = ["QB2", "RB9", "RB10", "WR1", "WR2", "WR3", "TE1", "QB7", "RB13", "WR14", "TE7"]


# ---------- value-only (no rosters) ----------

def test_equal_value_one_for_one_is_even(repo, league):
    result = evaluate_trade(trade(league, ["RB3"], ["WR3"]), repo)  # both 180 pts, VOR 80
    assert result.fairness.score == 100
    assert result.fairness.favored == "even"
    assert result.winner == "even"
    assert result.team_a.grade == result.team_b.grade == "C+"
    assert result.winner_basis == "value_only"


def test_lopsided_one_for_one(repo, league):
    result = evaluate_trade(trade(league, ["RB1"], ["RB9"]), repo)  # VOR 100 for VOR 20
    assert result.team_a.value_given == 100
    assert result.team_a.value_received == 20
    assert result.fairness.score == 20
    assert result.fairness.label == "Lopsided"
    assert result.winner == "team_b"
    assert result.team_a.grade == "F"
    assert result.team_b.grade == "A+"


def test_two_for_one_filler_does_not_inflate_value(repo, league):
    # Two below-replacement RBs (VOR 0 each) cannot buy a star.
    result = evaluate_trade(trade(league, ["RB13", "RB14"], ["RB2"]), repo)
    assert result.team_a.value_given == 0
    assert result.team_a.value_received == 90
    assert result.winner == "team_a"
    assert result.fairness.label == "Lopsided"


def test_no_roster_claims_without_rosters(repo, league):
    # Fair (90/100) with different grades, but no rosters: the "needs differ" sentence would be invented.
    result = evaluate_trade(trade(league, ["RB1"], ["RB2"]), repo)
    assert result.fairness.score == 90
    assert result.team_a.grade[0] != result.team_b.grade[0]
    assert not any("needs differ" in d for d in result.explanation.details)


def test_scoring_format_can_flip_the_winner(repo):
    # WR_PPR: 10 ppg standard / 16 ppg PPR.  RB8: 13 ppg in every format.
    ppr = evaluate_trade(trade(LeagueSettings(num_teams=4, scoring_format="ppr"), ["RB8"], ["WR_PPR"]), repo)
    std = evaluate_trade(trade(LeagueSettings(num_teams=4, scoring_format="standard"), ["RB8"], ["WR_PPR"]), repo)
    assert ppr.team_a.net_value > 0
    assert std.team_a.net_value < 0


# ---------- roster-aware ----------

def test_trade_that_helps_one_team_and_hurts_the_other(repo, league):
    # A sends a bench RB (RB12) for B's best starting WR.
    result = evaluate_trade(trade(league, ["RB12"], ["WR1"], ROSTER_A, ROSTER_B), repo)
    assert result.team_a.roster.lineup_delta > 0
    assert result.team_b.roster.lineup_delta < 0
    assert result.winner == "team_a"
    assert result.winner_basis == "roster_aware"
    assert result.team_a.grade_method == "roster_aware"


def test_lineup_delta_matches_hand_calculation(repo, league):
    # A before: QB1 240 | RB1 200, RB2 190 | WR9 120, WR10 110 | TE2 130 | FLEX RB3 180 -> 1170
    result = evaluate_trade(trade(league, ["RB3"], ["WR1"], ROSTER_A, ROSTER_B), repo)
    r = result.team_a.roster
    assert r.lineup_before.total_points == 1170
    # After: QB1 240, RB1 200, RB2 190, WR1 200, WR9 120, TE2 130, FLEX WR10 110 = 1190
    assert r.lineup_after.total_points == 1190
    assert r.lineup_delta == 20
    wr = next(p for p in r.positions if p.position == Position.WR)
    assert wr.starter_points_delta == 200


def test_complementary_needs_fair_trade_can_help_both(repo):
    # Without a FLEX, A's third RB and B's third WR are wasted on the bench.
    # Swapping them (identical value) lets both teams start a better player.
    no_flex = LeagueSettings(num_teams=4, scoring_format="standard", lineup=LineupSlots(FLEX=0))
    result = evaluate_trade(trade(no_flex, ["RB3"], ["WR3"], ROSTER_A, ROSTER_B), repo)
    assert result.fairness.score == 100
    assert result.team_a.roster.lineup_delta == 70  # WR3 180 replaces WR10 110
    assert result.team_b.roster.lineup_delta == 70  # RB3 180 replaces RB10 110


def test_flex_can_absorb_a_positional_swap(repo, league):
    # Same swap with a FLEX: A already started RB3 at FLEX, so the lineup total is unchanged.
    result = evaluate_trade(trade(league, ["RB3"], ["WR3"], ROSTER_A, ROSTER_B), repo)
    assert result.team_a.roster.lineup_delta == 0


def test_two_for_one_fills_open_spot_and_forces_drop(repo, league):
    full_b = ROSTER_B + ["RB14", "WR15", "TE8"]  # 14 = league max
    result = evaluate_trade(trade(league, ["RB3", "WR10"], ["WR1"], ROSTER_A, full_b), repo)
    a, b = result.team_a.roster, result.team_b.roster
    assert len(a.replacements_added) == 1  # A went from 11 to 10 players
    assert a.replacements_added == [Position.RB]  # tie -> like-for-like with the first traded player
    assert len(b.dropped_players) == 1  # B went from 14 to 15 players
    assert len(b.lineup_after.starters) + len(b.lineup_after.bench) == 14


def test_roster_aware_grade_uses_documented_table(repo, league):
    result = evaluate_trade(trade(league, ["RB3"], ["WR1"], ROSTER_A, ROSTER_B), repo)
    pct = result.team_a.roster.lineup_delta_pct
    assert result.team_a.grade_score == pct
    assert result.team_a.grade == letter_grade(pct, "roster_aware")


# ---------- validation & data quality ----------

def test_invalid_player_id(repo, league):
    with pytest.raises(UnknownPlayerError) as exc:
        evaluate_trade(trade(league, ["RB1"], ["NOT_A_PLAYER"]), repo)
    assert exc.value.player_ids == ["NOT_A_PLAYER"]


def test_duplicate_players_rejected(repo, league):
    with pytest.raises(TradeValidationError, match="Duplicate"):
        evaluate_trade(trade(league, ["RB1", "RB1"], ["WR1"]), repo)


def test_player_on_both_sides_rejected(repo, league):
    with pytest.raises(TradeValidationError, match="both sides"):
        evaluate_trade(trade(league, ["RB1"], ["RB1"]), repo)


def test_cannot_trade_player_not_on_roster(repo, league):
    with pytest.raises(TradeValidationError, match="not on its roster"):
        evaluate_trade(trade(league, ["RB5"], ["WR1"], ROSTER_A, ROSTER_B), repo)


def test_roster_over_league_max_rejected(repo, league):
    big = ROSTER_A + ["RB14", "WR15", "TE8", "QB8"]  # 15 > 14
    with pytest.raises(TradeValidationError, match="maximum"):
        evaluate_trade(trade(league, ["RB1"], ["WR1"], big, None), repo)


def test_missing_projection_produces_warning(repo, league):
    result = evaluate_trade(trade(league, ["RB_NOPROJ"], ["WR16"]), repo)
    assert any("no projection" in w for w in result.warnings)
    assert result.players_given[0].projection_available is False


def test_injury_status_is_reported_in_explanation(repo, league):
    result = evaluate_trade(trade(league, ["RB5"], ["WR_HURT"]), repo)
    assert any("OUT" in d for d in result.explanation.details)


def test_fairness_score_is_a_whole_number_rounded_half_up():
    from app.services.grading import fairness

    assert fairness(84.5, 100)[0] == 85  # Python's round() would give 84
    assert fairness(84.4, 100)[0] == 84


@pytest.mark.parametrize(
    "score, grade",
    [(6.0, "A+"), (5.99, "A"), (0.0, "C+"), (-0.01, "C"), (-4.5, "D-"), (-4.51, "F")],
)
def test_grade_boundaries(score, grade):
    assert letter_grade(score, "roster_aware") == grade
