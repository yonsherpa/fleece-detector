"""Request and response schemas for trade evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.league import LeagueSettings, Position
from app.models.player import DatasetInfo, PlayerValue


class TradeRequest(BaseModel):
    team_a_gives: list[str] = Field(min_length=1, max_length=8)
    team_a_receives: list[str] = Field(min_length=1, max_length=8)
    team_a_roster: list[str] | None = Field(
        None, description="Team A's full roster (including players it gives). Enables roster-aware grading."
    )
    team_b_roster: list[str] | None = Field(
        None, description="Team B's full roster (including players it gives). Enables roster-aware grading."
    )
    league: LeagueSettings = Field(default_factory=LeagueSettings)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "team_a_gives": ["sleeper-9221"],
                    "team_a_receives": ["sleeper-9488"],
                    "league": {"num_teams": 12, "scoring_format": "ppr"},
                }
            ]
        }
    }


GradeMethod = Literal["roster_aware", "value_only"]


class LineupSlotAssignment(BaseModel):
    slot: str
    player_id: str
    name: str
    position: Position
    projected_ros_points: float
    is_replacement: bool = Field(
        False, description="True for a waiver-level placeholder that fills an open roster spot."
    )


class LineupSnapshot(BaseModel):
    total_points: float
    starters: list[LineupSlotAssignment]
    bench: list[LineupSlotAssignment]


class PositionImpact(BaseModel):
    position: Position
    starter_points_before: float
    starter_points_after: float
    starter_points_delta: float
    roster_count_before: int
    roster_count_after: int
    top_backup_points_before: float | None = Field(
        description="Projected points of the best bench player at this position (depth)."
    )
    top_backup_points_after: float | None


class RosterImpact(BaseModel):
    lineup_before: LineupSnapshot
    lineup_after: LineupSnapshot
    lineup_delta: float
    lineup_delta_pct: float
    positions: list[PositionImpact]
    dropped_players: list[str] = Field(description="Names dropped to satisfy the roster size limit.")
    replacements_added: list[Position] = Field(
        description="Positions of waiver-level players added to fill roster spots opened by the trade."
    )


class TeamImpact(BaseModel):
    grade: str
    grade_method: GradeMethod
    grade_score: float = Field(description="The percentage the grade was derived from (see README).")
    value_given: float = Field(description="Sum of value over replacement sent away.")
    value_received: float = Field(description="Sum of value over replacement received.")
    net_value: float
    roster: RosterImpact | None = None


class Fairness(BaseModel):
    score: float = Field(ge=0, le=100, description="100 = identical value on both sides.")
    label: str
    favored: Literal["team_a", "team_b", "even"]


class Explanation(BaseModel):
    summary: str
    details: list[str]


class TradeEvaluation(BaseModel):
    grade: str = Field(description="Team A's grade (the user's perspective).")
    winner: Literal["team_a", "team_b", "even"]
    winner_basis: GradeMethod
    fairness: Fairness
    team_a: TeamImpact
    team_b: TeamImpact
    players_given: list[PlayerValue]
    players_received: list[PlayerValue]
    explanation: Explanation
    warnings: list[str]
    league: LeagueSettings
    dataset: DatasetInfo
