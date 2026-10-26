"""Pure transform: raw Sleeper + nflverse data -> one row per fantasy-relevant player.

No network access here, so the logic is unit-tested with small hand-made inputs.

Rest-of-season projection
-------------------------
For every game a player's team has left (from the nflverse schedule), add up that
week's Sleeper projected stat line. Weeks where Sleeper projects nothing (e.g. the
player is ruled out) contribute 0. The result is stored as an average per remaining
game, so `per_game x games_remaining` reproduces the season-long total exactly and
the valuation engine can apply any league's scoring rules to it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

# Sleeper abbreviation -> nflverse schedule abbreviation, where they differ.
TEAM_ALIASES = {"LAR": "LA"}

# Sleeper stat key -> our PlayerProjection field.
STAT_MAP = {
    "pass_yd": "pass_yds",
    "pass_td": "pass_tds",
    "pass_int": "pass_ints",
    "rush_yd": "rush_yds",
    "rush_td": "rush_tds",
    "rec": "receptions",
    "rec_yd": "rec_yds",
    "rec_td": "rec_tds",
    "fum_lost": "fumbles_lost",
}
TWO_PT_KEYS = ("pass_2pt", "rush_2pt", "rec_2pt")
STAT_COLUMNS = [*STAT_MAP.values(), "two_pt_conversions"]

MIN_ROS_PPR_POINTS = 1.0  # drop players projected for essentially nothing


def remaining_weeks(schedule: pd.DataFrame, season: int, current_week: int) -> dict[str, list[int]]:
    """Weeks each team still has to play (regular season, not yet completed)."""
    games = schedule[
        (schedule["season"] == season)
        & (schedule["game_type"] == "REG")
        & (schedule["week"] >= current_week)
        & (schedule["result"].isna())
    ]
    weeks: dict[str, list[int]] = {}
    for row in games.itertuples():
        for team in (row.home_team, row.away_team):
            weeks.setdefault(team, []).append(int(row.week))
    return {team: sorted(w) for team, w in weeks.items()}


def bye_weeks(schedule: pd.DataFrame, season: int) -> dict[str, int]:
    games = schedule[(schedule["season"] == season) & (schedule["game_type"] == "REG")]
    all_weeks = set(games["week"])
    byes: dict[str, int] = {}
    for team in set(games["home_team"]) | set(games["away_team"]):
        played = set(games.loc[(games["home_team"] == team) | (games["away_team"] == team), "week"])
        missing = sorted(all_weeks - played)
        if missing:
            byes[team] = missing[0]
    return byes


def fantasy_position(player: dict[str, Any]) -> str | None:
    """The QB/RB/WR/TE position a player counts as in fantasy, or None.

    Usually the listed position, but two-way players and fullbacks are listed elsewhere
    (Travis Hunter is "DB", fullbacks are "FB") while being fantasy-eligible at WR/RB.
    """
    if player.get("position") in SKILL_POSITIONS:
        return player["position"]
    return next((p for p in player.get("fantasy_positions") or [] if p in SKILL_POSITIONS), None)


def _clean_injury(status: Any) -> str | None:
    if not status or not isinstance(status, str):
        return None
    return status.strip().upper() or None


def build_players(
    players: dict[str, dict[str, Any]],
    weekly_projections: dict[int, dict[str, dict[str, Any]]],
    schedule: pd.DataFrame,
    season: int,
    current_week: int,
) -> pd.DataFrame:
    remaining = remaining_weeks(schedule, season, current_week)
    byes = bye_weeks(schedule, season)

    rows = []
    for sleeper_id, p in players.items():
        position = fantasy_position(p)
        if position is None or not p.get("team") or not p.get("active"):
            continue
        team = p["team"]
        schedule_team = TEAM_ALIASES.get(team, team)
        weeks = remaining.get(schedule_team, [])
        if not weeks:
            continue

        totals = dict.fromkeys(STAT_COLUMNS, 0.0)
        ros_ppr = 0.0
        for week in weeks:
            stats = weekly_projections.get(week, {}).get(sleeper_id)
            if not stats or stats.get("pts_ppr") is None:
                continue
            ros_ppr += stats["pts_ppr"]
            for key, column in STAT_MAP.items():
                totals[column] += stats.get(key) or 0.0
            totals["two_pt_conversions"] += sum(stats.get(k) or 0.0 for k in TWO_PT_KEYS)

        if ros_ppr < MIN_ROS_PPR_POINTS:
            continue

        name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        rows.append(
            {
                "player_id": f"sleeper-{sleeper_id}",
                "name": name,
                "position": position,
                "nfl_team": team,
                "bye_week": byes.get(schedule_team),
                "games_remaining": len(weeks),
                "injury_status": _clean_injury(p.get("injury_status")),
                "espn_id": p.get("espn_id"),
                "gsis_id": p.get("gsis_id"),
                **{c: round(v / len(weeks), 3) for c, v in totals.items()},
            }
        )

    columns = [
        "player_id", "name", "position", "nfl_team", "bye_week", "games_remaining",
        "injury_status", "espn_id", "gsis_id", *STAT_COLUMNS,
    ]
    df = pd.DataFrame(rows, columns=columns)
    for col in ("bye_week", "espn_id"):
        df[col] = df[col].astype("Int64")
    return df.sort_values("player_id").reset_index(drop=True)
