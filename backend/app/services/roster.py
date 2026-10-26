"""Stage 2: roster-aware evaluation.

    trade impact = optimal lineup points AFTER trade - optimal lineup points BEFORE trade

Roster constraints are applied to the post-trade roster:
  * Too many players (e.g. receiving 2-for-1): drop whichever player costs the
    optimal lineup the least, repeatedly, until the roster fits.
  * Spots opened by the trade (e.g. sending 2-for-1): fill each with a
    waiver-level player at whichever position helps the lineup most. Without
    this, consolidation trades would look worse than they are, because a real
    manager would pick someone up.
"""

from __future__ import annotations

from app.models.league import LeagueSettings, Position
from app.models.trade import LineupSlotAssignment, LineupSnapshot, PositionImpact, RosterImpact
from app.services.lineup import OptimalLineup, RosterEntry, optimize_lineup
from app.services.valuation import Valuation


def roster_entry(player_id: str, valuation: Valuation) -> RosterEntry:
    v = valuation.values[player_id]
    return RosterEntry(player_id, v.name, v.position, v.projected_ros_points)


def _snapshot(lineup: OptimalLineup) -> LineupSnapshot:
    def row(slot: str, e: RosterEntry) -> LineupSlotAssignment:
        return LineupSlotAssignment(
            slot=slot,
            player_id=e.player_id,
            name=e.name,
            position=e.position,
            projected_ros_points=e.points,
            is_replacement=e.is_replacement,
        )

    return LineupSnapshot(
        total_points=lineup.total_points,
        starters=[row(slot, e) for slot, e in lineup.starters],
        bench=[row("BENCH", e) for e in lineup.bench],
    )


def enforce_max_size(
    entries: list[RosterEntry], slots: list[str], max_size: int
) -> tuple[list[RosterEntry], list[RosterEntry]]:
    dropped: list[RosterEntry] = []
    while len(entries) > max_size:
        # Try dropping each player (weakest first, so ties drop the weaker player).
        candidates = sorted(entries, key=lambda e: (e.points, e.player_id))
        best_total, best_drop = float("-inf"), candidates[0]
        for cand in candidates:
            remaining = [e for e in entries if e is not cand]
            total = optimize_lineup(remaining, slots).total_points
            if total > best_total:
                best_total, best_drop = total, cand
        entries = [e for e in entries if e is not best_drop]
        dropped.append(best_drop)
    return entries, dropped


def _fill_open_spots(
    entries: list[RosterEntry],
    slots: list[str],
    open_spots: int,
    valuation: Valuation,
    preferred: list[Position],
) -> tuple[list[RosterEntry], list[Position]]:
    # When no position helps the lineup more than another, replace like-for-like:
    # positions the team just traded away are tried first and win ties.
    order = list(dict.fromkeys([*preferred, *Position]))
    added: list[Position] = []
    for k in range(open_spots):
        best_total, best_entry = float("-inf"), None
        for pos in order:
            cand = RosterEntry(
                player_id=f"WAIVER-{pos.value}-{k + 1}",
                name=f"Waiver-level {pos.value}",
                position=pos,
                points=valuation.waiver_points[pos],
                is_replacement=True,
            )
            total = optimize_lineup([*entries, cand], slots).total_points
            if total > best_total:
                best_total, best_entry = total, cand
        assert best_entry is not None
        entries = [*entries, best_entry]
        added.append(best_entry.position)
    return entries, added


def _position_impacts(before: OptimalLineup, after: OptimalLineup) -> list[PositionImpact]:
    def starter_points(lineup: OptimalLineup, pos: Position) -> float:
        return round(sum(e.points for _, e in lineup.starters if e.position == pos), 2)

    def count(lineup: OptimalLineup, pos: Position) -> int:
        return sum(1 for _, e in lineup.starters if e.position == pos) + sum(
            1 for e in lineup.bench if e.position == pos
        )

    def top_backup(lineup: OptimalLineup, pos: Position) -> float | None:
        pts = [e.points for e in lineup.bench if e.position == pos]
        return max(pts) if pts else None

    impacts = []
    for pos in Position:
        b, a = starter_points(before, pos), starter_points(after, pos)
        impacts.append(
            PositionImpact(
                position=pos,
                starter_points_before=b,
                starter_points_after=a,
                starter_points_delta=round(a - b, 2),
                roster_count_before=count(before, pos),
                roster_count_after=count(after, pos),
                top_backup_points_before=top_backup(before, pos),
                top_backup_points_after=top_backup(after, pos),
            )
        )
    return impacts


def evaluate_roster_change(
    roster_ids: list[str],
    outgoing_ids: list[str],
    incoming_ids: list[str],
    valuation: Valuation,
    league: LeagueSettings,
) -> RosterImpact:
    slots = league.lineup.starting_slots()
    max_size = league.lineup.max_roster_size

    before_entries = [roster_entry(pid, valuation) for pid in roster_ids]
    before = optimize_lineup(before_entries, slots)

    outgoing = set(outgoing_ids)
    after_entries = [e for e in before_entries if e.player_id not in outgoing]
    after_entries += [roster_entry(pid, valuation) for pid in incoming_ids]

    after_entries, dropped = enforce_max_size(after_entries, slots, max_size)
    open_spots = max(0, min(len(before_entries), max_size) - len(after_entries))
    traded_away = [e.position for e in before_entries if e.player_id in outgoing]
    after_entries, added = _fill_open_spots(after_entries, slots, open_spots, valuation, traded_away)

    after = optimize_lineup(after_entries, slots)
    delta = round(after.total_points - before.total_points, 2)
    delta_pct = round(100 * delta / max(before.total_points, 1.0), 2)

    return RosterImpact(
        lineup_before=_snapshot(before),
        lineup_after=_snapshot(after),
        lineup_delta=delta,
        lineup_delta_pct=delta_pct,
        positions=_position_impacts(before, after),
        dropped_players=[e.name for e in dropped],
        replacements_added=added,
    )
