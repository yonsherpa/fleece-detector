"""Orchestrates a full trade evaluation: validate -> value -> roster impact -> grade -> explain."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.player import DatasetInfo, PlayerValue
from app.models.trade import Fairness, TeamImpact, TradeEvaluation, TradeRequest
from app.services import grading
from app.services.errors import TradeValidationError
from app.services.explanations import build_explanation
from app.services.player_repository import PlayerRepository
from app.services.roster import evaluate_roster_change
from app.services.valuation import Valuation


def _duplicates(ids: list[str]) -> list[str]:
    seen, dupes = set(), set()
    for pid in ids:
        (dupes if pid in seen else seen).add(pid)
    return sorted(dupes)


def _validate(req: TradeRequest, repo: PlayerRepository) -> None:
    for label, ids in [
        ("team_a_gives", req.team_a_gives),
        ("team_a_receives", req.team_a_receives),
        ("team_a_roster", req.team_a_roster or []),
        ("team_b_roster", req.team_b_roster or []),
    ]:
        if dupes := _duplicates(ids):
            raise TradeValidationError(f"Duplicate player(s) in {label}: {', '.join(dupes)}")

    if overlap := set(req.team_a_gives) & set(req.team_a_receives):
        raise TradeValidationError(f"Player(s) on both sides of the trade: {', '.join(sorted(overlap))}")

    repo.require_known(
        req.team_a_gives + req.team_a_receives + (req.team_a_roster or []) + (req.team_b_roster or [])
    )

    max_size = req.league.lineup.max_roster_size
    for team, roster, gives, other_side in [
        ("Team A", req.team_a_roster, req.team_a_gives, req.team_a_receives),
        ("Team B", req.team_b_roster, req.team_a_receives, req.team_a_gives),
    ]:
        if roster is None:
            continue
        if missing := set(gives) - set(roster):
            raise TradeValidationError(
                f"{team} cannot trade player(s) not on its roster: {', '.join(sorted(missing))}"
            )
        if already := set(other_side) & set(roster):
            raise TradeValidationError(
                f"{team} already rosters player(s) it would receive: {', '.join(sorted(already))}"
            )
        if len(roster) > max_size:
            raise TradeValidationError(
                f"{team} roster has {len(roster)} players; league maximum is {max_size}."
            )

    if req.team_a_roster and req.team_b_roster:
        if shared := set(req.team_a_roster) & set(req.team_b_roster):
            raise TradeValidationError(f"Player(s) on both rosters: {', '.join(sorted(shared))}")


def _team_impact(
    roster: list[str] | None,
    gives: list[str],
    receives: list[str],
    valuation: Valuation,
    req: TradeRequest,
) -> TeamImpact:
    given = round(sum(valuation.values[p].value_over_replacement for p in gives), 2)
    received = round(sum(valuation.values[p].value_over_replacement for p in receives), 2)

    if roster is not None:
        impact = evaluate_roster_change(roster, gives, receives, valuation, req.league)
        method, score = "roster_aware", impact.lineup_delta_pct
    else:
        impact, method, score = None, "value_only", grading.value_only_score(received, given)

    return TeamImpact(
        grade=grading.letter_grade(score, method),
        grade_method=method,
        grade_score=score,
        value_given=given,
        value_received=received,
        net_value=round(received - given, 2),
        roster=impact,
    )


STALE_AFTER = timedelta(days=3)  # projections move every week; older data deserves a heads-up


def _warnings(players: list[PlayerValue], dataset: DatasetInfo, now: datetime | None = None) -> list[str]:
    warnings = [
        f"{p.name} ({p.player_id}) has no projection in the current dataset and is valued at 0 points."
        for p in players
        if not p.projection_available
    ]
    if dataset.is_sample:
        warnings.append("Evaluated with a SYNTHETIC sample dataset; players and projections are fictional.")
    try:
        as_of = datetime.fromisoformat(dataset.as_of)
    except ValueError:
        warnings.append("The projection data has no reliable timestamp, so it may be out of date.")
    else:
        age = (now or datetime.now(timezone.utc)) - as_of
        if age > STALE_AFTER:
            warnings.append(
                f"Projections were last updated {age.days} days ago (week {dataset.week}); "
                "values may not reflect recent injuries or depth chart changes."
            )
    return warnings


def evaluate_trade(req: TradeRequest, repo: PlayerRepository) -> TradeEvaluation:
    _validate(req, repo)
    valuation = repo.valuation(req.league)

    team_a = _team_impact(req.team_a_roster, req.team_a_gives, req.team_a_receives, valuation, req)
    team_b = _team_impact(req.team_b_roster, req.team_a_receives, req.team_a_gives, valuation, req)

    score, label, favored = grading.fairness(team_a.value_received, team_b.value_received)
    fairness = Fairness(score=score, label=label, favored=favored)

    if team_a.roster and team_b.roster:
        winner_basis = "roster_aware"
        gap = team_a.roster.lineup_delta_pct - team_b.roster.lineup_delta_pct
        if abs(gap) < grading.WINNER_EVEN_THRESHOLD_PCT:
            winner = "even"
        else:
            winner = "team_a" if gap > 0 else "team_b"
    else:
        winner_basis, winner = "value_only", favored

    given = [valuation.values[p] for p in req.team_a_gives]
    received = [valuation.values[p] for p in req.team_a_receives]

    return TradeEvaluation(
        grade=team_a.grade,
        winner=winner,
        winner_basis=winner_basis,
        fairness=fairness,
        team_a=team_a,
        team_b=team_b,
        players_given=given,
        players_received=received,
        explanation=build_explanation(team_a, team_b, fairness, given, received),
        warnings=_warnings(given + received, repo.dataset),
        league=req.league,
        dataset=repo.dataset,
    )
