"""Stage 1: baseline player value (value over replacement).

Raw projected points are not comparable across positions: a QB scoring 300 points
is worth less than it looks if the 13th-best QB scores 280. We therefore value
players by how much they out-score a *replacement-level* player at their position.

Replacement level is derived from the league itself:
  1. Fill every team's dedicated slots (num_teams x QB/RB/WR/TE slots).
  2. Fill FLEX / SUPERFLEX slots league-wide with the best remaining eligible players.
  3. The best player at each position who would NOT start anywhere is "replacement".

Because players below replacement are worth 0, adding filler players to a trade
does not inflate its value -- this is what keeps 3-for-1 trades honest.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.league import SLOT_ELIGIBILITY, LeagueSettings, Position
from app.models.player import Player, PlayerValue
from app.services.scoring import fantasy_points_per_game


@dataclass(frozen=True)
class Valuation:
    values: dict[str, PlayerValue]
    replacement_points: dict[Position, float]
    """ROS points of the best non-starter at each position (used for VOR)."""
    waiver_points: dict[Position, float]
    """ROS points of the best player who is likely unrostered (used to fill open roster spots)."""
    starter_demand: dict[Position, int]


def _pool_value(pools: dict[Position, list[float]], pos: Position, index: int) -> float:
    pool = pools[pos]
    return pool[index] if index < len(pool) else 0.0


def _starter_demand(pools: dict[Position, list[float]], league: LeagueSettings) -> dict[Position, int]:
    """How many players at each position start league-wide, including flex usage."""
    n = league.num_teams
    demand = {pos: n * getattr(league.lineup, pos.value) for pos in Position}

    for flex_slot in ("FLEX", "SUPERFLEX"):
        eligible = sorted(SLOT_ELIGIBILITY[flex_slot], key=lambda p: p.value)
        for _ in range(n * getattr(league.lineup, flex_slot)):
            best_pos: Position | None = None
            best_points = float("-inf")
            for pos in eligible:
                if demand[pos] < len(pools[pos]) and pools[pos][demand[pos]] > best_points:
                    best_pos, best_points = pos, pools[pos][demand[pos]]
            if best_pos is None:
                break
            demand[best_pos] += 1
    return demand


def build_valuation(players: list[Player], league: LeagueSettings) -> Valuation:
    scoring = league.resolved_scoring()

    ppg: dict[str, float | None] = {}
    ros: dict[str, float] = {}
    for p in players:
        ppg[p.player_id] = fantasy_points_per_game(p, scoring)
        ros[p.player_id] = round((ppg[p.player_id] or 0.0) * p.games_remaining, 2)

    # Per-position pools of projected players, best first (ties broken by id for determinism).
    ranked: dict[Position, list[Player]] = {pos: [] for pos in Position}
    for p in players:
        if ppg[p.player_id] is not None:
            ranked[p.position].append(p)
    for pos in Position:
        ranked[pos].sort(key=lambda p: (-ros[p.player_id], p.player_id))
    pools = {pos: [ros[p.player_id] for p in ranked[pos]] for pos in Position}

    demand = _starter_demand(pools, league)
    replacement = {pos: _pool_value(pools, pos, demand[pos]) for pos in Position}

    # Waiver level: spread all rostered spots across positions in proportion to starter demand.
    total_demand = sum(demand.values()) or 1
    rostered_spots = league.num_teams * league.lineup.max_roster_size
    waiver = {
        pos: _pool_value(pools, pos, round(demand[pos] * rostered_spots / total_demand))
        for pos in Position
    }

    rank = {p.player_id: i + 1 for pos in Position for i, p in enumerate(ranked[pos])}
    values = {
        p.player_id: PlayerValue(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            nfl_team=p.nfl_team,
            bye_week=p.bye_week,
            injury_status=p.injury_status,
            games_remaining=p.games_remaining,
            projection_available=ppg[p.player_id] is not None,
            projected_ppg=ppg[p.player_id],
            projected_ros_points=ros[p.player_id],
            replacement_ros_points=replacement[p.position],
            value_over_replacement=round(max(0.0, ros[p.player_id] - replacement[p.position]), 2),
            positional_rank=rank.get(p.player_id),
        )
        for p in players
    }
    return Valuation(
        values=values,
        replacement_points=replacement,
        waiver_points=waiver,
        starter_demand=demand,
    )
