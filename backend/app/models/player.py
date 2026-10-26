"""Player, projection, and dataset models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.league import Position

# Input limits for request bodies, so a client can't send huge payloads to tie up the server.
# The largest legal roster is 20 starters + 12 bench = 32 players.
PlayerId = Annotated[str, StringConstraints(min_length=1, max_length=40)]
MAX_ROSTER_IDS = 40


class PlayerProjection(BaseModel):
    """Projected per-game stat line. Converted to fantasy points using league scoring."""

    pass_yds: float = 0.0
    pass_tds: float = 0.0
    pass_ints: float = 0.0
    rush_yds: float = 0.0
    rush_tds: float = 0.0
    receptions: float = 0.0
    rec_yds: float = 0.0
    rec_tds: float = 0.0
    fumbles_lost: float = 0.0
    two_pt_conversions: float = 0.0


class Player(BaseModel):
    player_id: str
    name: str
    position: Position
    nfl_team: str
    bye_week: int | None = None
    games_remaining: int = Field(ge=0, le=18)
    injury_status: str | None = Field(
        None, description="Reported as-is from the data source (e.g. QUESTIONABLE, OUT)."
    )
    projection: PlayerProjection | None = Field(
        None, description="None means the data source has no projection for this player."
    )
    espn_id: int | None = Field(None, description="Cross-source id, used to match ESPN rosters.")
    gsis_id: str | None = Field(None, description="NFL GSIS id, the key nflverse datasets use.")


class DatasetInfo(BaseModel):
    source: str
    is_sample: bool
    as_of: str = Field(description="ISO-8601 timestamp of when the projections were produced.")
    season: int | None = None
    week: int | None = None
    description: str


class PlayerValue(BaseModel):
    """A player's computed value under specific league settings."""

    player_id: str
    name: str
    position: Position
    nfl_team: str
    bye_week: int | None
    injury_status: str | None
    games_remaining: int
    projection_available: bool
    projected_ppg: float | None = Field(description="Projected fantasy points per game.")
    projected_ros_points: float = Field(description="projected_ppg x games_remaining.")
    replacement_ros_points: float = Field(
        description="Rest-of-season points of a replacement-level player at this position."
    )
    value_over_replacement: float = Field(
        description="max(0, projected_ros_points - replacement_ros_points)."
    )
    positional_rank: int | None


class PlayerListResponse(BaseModel):
    players: list[PlayerValue]
    total: int
    dataset: DatasetInfo
