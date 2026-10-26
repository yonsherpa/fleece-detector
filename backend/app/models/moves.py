"""Schemas for roster move suggestions (the Moves tab)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.league import LeagueSettings
from app.models.player import DatasetInfo, PlayerValue


class LeagueTeamRoster(BaseModel):
    team_name: str
    player_ids: list[str]


class MovesRequest(BaseModel):
    roster: list[str] | None = Field(None, description="Your roster's player ids. Unlocks roster-specific sections.")
    league: LeagueSettings = Field(default_factory=LeagueSettings)
    league_rosters: list[LeagueTeamRoster] | None = Field(
        None,
        description="Every team's roster (e.g. from an ESPN import). Makes waiver targets real free agents "
        "and limits buy targets to players other teams own.",
    )


class MoveSuggestion(BaseModel):
    player: PlayerValue
    lineup_change: float | None = Field(
        None,
        description="Projected ROS points your best lineup gains (+) by adding or loses (-) by removing the "
        "player. None when no roster was given.",
    )
    drop_to_make_room: str | None = Field(None, description="Who you'd drop if your roster is full.")
    trend_count: int | None = Field(None, description="Sleeper adds/drops in the lookback window.")
    on_your_roster: bool = False
    owner_team: str | None = Field(None, description="Which league team has this player, when rosters are known.")
    reason: str


class TrendingInfo(BaseModel):
    available: bool
    message: str | None = None
    lookback_hours: int
    fetched_at: str | None = None
    unprojected_count: int = Field(0, description="Trending players with no projection in our dataset.")


class MovesResponse(BaseModel):
    has_roster: bool
    sell_high: list[MoveSuggestion]
    safe_to_drop: list[MoveSuggestion]
    trending_adds: list[MoveSuggestion]
    trending_drops: list[MoveSuggestion]
    waiver_targets: list[MoveSuggestion]
    buy_targets: list[MoveSuggestion]
    buy_budget: float | None = Field(
        None, description="Buy targets are limited to roughly this value: your best sell-high player's value."
    )
    rostered_cutoff: int = Field(description="Players ranked beyond this are likely unrostered in your league.")
    availability: Literal["league", "estimated"] = Field(
        description="'league' when waiver targets come from real league rosters, 'estimated' when from rank."
    )
    trending: TrendingInfo
    notes: list[str]
    league: LeagueSettings
    dataset: DatasetInfo
