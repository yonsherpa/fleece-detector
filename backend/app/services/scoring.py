"""Convert projected stat lines into fantasy points for a league's scoring rules."""

from __future__ import annotations

from app.models.league import Position, ScoringSettings
from app.models.player import Player


def fantasy_points_per_game(player: Player, scoring: ScoringSettings) -> float | None:
    """Projected fantasy points per game, or None if the player has no projection."""
    proj = player.projection
    if proj is None:
        return None

    reception_value = scoring.reception
    if player.position == Position.TE:
        reception_value += scoring.te_reception_bonus

    points = (
        proj.pass_yds * scoring.pass_yd
        + proj.pass_tds * scoring.pass_td
        + proj.pass_ints * scoring.pass_int
        + proj.rush_yds * scoring.rush_yd
        + proj.rush_tds * scoring.rush_td
        + proj.receptions * reception_value
        + proj.rec_yds * scoring.rec_yd
        + proj.rec_tds * scoring.rec_td
        + proj.fumbles_lost * scoring.fumble_lost
        + proj.two_pt_conversions * scoring.two_pt_conversion
    )
    return round(points, 2)
