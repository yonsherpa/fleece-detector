"""Optimal starting lineup selection.

Choosing a lineup is a maximum-weight bipartite matching between players and
slots: each slot gets at most one player, each player fills at most one slot,
and a player can only fill slots their position is eligible for. Greedy "best
player first" can fail once FLEX/SUPERFLEX slots overlap with dedicated ones, so
we solve it exactly with the Hungarian algorithm (scipy's linear_sum_assignment).

Trick: we add one "empty" dummy row per slot worth 0 points everywhere. That
lets a slot stay empty when no eligible player exists, instead of forcing an
ineligible player into it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.models.league import SLOT_ELIGIBILITY, Position

_INELIGIBLE = -1e9


@dataclass(frozen=True)
class RosterEntry:
    player_id: str
    name: str
    position: Position
    points: float
    is_replacement: bool = False


@dataclass(frozen=True)
class OptimalLineup:
    starters: list[tuple[str, RosterEntry]]  # (slot, player), in slot order
    bench: list[RosterEntry]
    total_points: float


def optimize_lineup(entries: list[RosterEntry], slots: list[str]) -> OptimalLineup:
    # Deterministic input order -> deterministic tie-breaking.
    players = sorted(entries, key=lambda e: (-e.points, e.player_id))
    n_players, n_slots = len(players), len(slots)
    if n_slots == 0:
        return OptimalLineup(starters=[], bench=players, total_points=0.0)

    weights = np.zeros((n_players + n_slots, n_slots))
    for i, entry in enumerate(players):
        for j, slot in enumerate(slots):
            weights[i, j] = entry.points if entry.position in SLOT_ELIGIBILITY[slot] else _INELIGIBLE

    rows, cols = linear_sum_assignment(weights, maximize=True)

    starters: list[tuple[int, str, RosterEntry]] = []
    used: set[int] = set()
    for i, j in zip(rows, cols):
        if i < n_players and weights[i, j] > _INELIGIBLE / 2:
            starters.append((j, slots[j], players[i]))
            used.add(i)
    starters.sort(key=lambda s: s[0])

    bench = [p for i, p in enumerate(players) if i not in used]
    total = round(sum(entry.points for _, _, entry in starters), 2)
    return OptimalLineup(
        starters=[(slot, entry) for _, slot, entry in starters],
        bench=bench,
        total_points=total,
    )
