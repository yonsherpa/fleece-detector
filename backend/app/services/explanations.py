"""Deterministic, template-based trade explanations.

Every sentence is generated from numbers the evaluator actually calculated, so
the explanation can never claim something the model did not compute. An LLM
could later rephrase these facts, but it would be given only this structured
output as input.
"""

from __future__ import annotations

from app.models.player import PlayerValue
from app.models.trade import Explanation, Fairness, RosterImpact, TeamImpact

STARTER_CHANGE_MIN = 0.5  # ROS points; smaller moves are noise
DEPTH_CHANGE_MIN = 5.0


def _backup(points: float | None, pos: str) -> str:
    return f"no bench {pos}" if points is None else f"{points:.1f} projected points"


def _team_summary(team_label: str, impact: TeamImpact) -> str:
    if impact.roster is not None:
        r = impact.roster
        if r.lineup_delta > 0:
            verb = "improves"
        elif r.lineup_delta < 0:
            verb = "lowers"
        else:
            return f"This trade does not change {team_label}'s projected starting lineup (grade {impact.grade})."
        return (
            f"This trade {verb} {team_label}'s projected starting lineup by "
            f"{abs(r.lineup_delta):.1f} rest-of-season points ({r.lineup_delta_pct:+.1f}%), "
            f"for a grade of {impact.grade}."
        )
    return (
        f"Without {team_label}'s roster, the grade compares value over replacement: "
        f"{team_label} sends {impact.value_given:.1f} and receives {impact.value_received:.1f} "
        f"points of value over replacement (grade {impact.grade})."
    )


def _roster_details(team_label: str, r: RosterImpact) -> list[str]:
    details: list[str] = []
    for p in r.positions:
        pos = p.position.value
        if abs(p.starter_points_delta) >= STARTER_CHANGE_MIN:
            direction = "rises" if p.starter_points_delta > 0 else "falls"
            details.append(
                f"{team_label}'s starting {pos} production {direction} by "
                f"{abs(p.starter_points_delta):.1f} points "
                f"({p.starter_points_before:.1f} -> {p.starter_points_after:.1f})."
            )
        before, after = p.top_backup_points_before, p.top_backup_points_after
        depth_lost = (before is not None and after is None) or (
            before is not None and after is not None and before - after >= DEPTH_CHANGE_MIN
        )
        depth_gained = (before is None and after is not None) or (
            before is not None and after is not None and after - before >= DEPTH_CHANGE_MIN
        )
        if depth_lost:
            details.append(
                f"{team_label}'s {pos} depth thins: best bench {pos} goes from {_backup(before, pos)} "
                f"to {_backup(after, pos)}, leaving less cover for injuries or byes."
            )
        elif depth_gained:
            details.append(
                f"{team_label}'s {pos} depth improves: best bench {pos} goes from {_backup(before, pos)} "
                f"to {_backup(after, pos)}."
            )
    if r.dropped_players:
        details.append(
            f"To stay within the roster limit, {team_label} would drop: {', '.join(r.dropped_players)}."
        )
    if r.replacements_added:
        positions = ", ".join(p.value for p in r.replacements_added)
        details.append(
            f"The trade opens {len(r.replacements_added)} roster spot(s) for {team_label}, "
            f"assumed filled by waiver-level player(s) at: {positions}."
        )
    return details


def _injury_notes(players: list[PlayerValue]) -> list[str]:
    return [
        f"{p.name} is listed as {p.injury_status} by the data source. Weeks the projections expect "
        f"{p.name} to miss already count as 0 in their rest-of-season value."
        for p in players
        if p.injury_status and p.injury_status.upper() != "ACTIVE"
    ]


def build_explanation(
    team_a: TeamImpact,
    team_b: TeamImpact,
    fairness: Fairness,
    players_given: list[PlayerValue],
    players_received: list[PlayerValue],
) -> Explanation:
    summary_parts = [_team_summary("Team A", team_a)]
    if fairness.favored == "even":
        summary_parts.append(f"Value exchanged is balanced (fairness {fairness.score:.0f}/100).")
    else:
        side = "Team A" if fairness.favored == "team_a" else "Team B"
        summary_parts.append(
            f"Trade fairness is {fairness.score:.0f}/100 ({fairness.label.lower()}), "
            f"with more value going to {side}."
        )

    details: list[str] = []
    if team_a.roster:
        details += _roster_details("Team A", team_a.roster)
    details.append(_team_summary("Team B", team_b))
    if team_b.roster:
        details += _roster_details("Team B", team_b.roster)

    # Only claim the teams' needs differ when both rosters were actually analyzed.
    rosters_known = team_a.roster is not None and team_b.roster is not None
    if rosters_known and fairness.score >= 80 and team_a.grade[0] != team_b.grade[0]:
        details.append(
            "The value exchanged is fair, but the teams' needs differ, so the trade helps one "
            "roster more than the other. A fair trade is not automatically good for both sides."
        )
    details += _injury_notes(players_given + players_received)
    return Explanation(summary=" ".join(summary_parts), details=details)
