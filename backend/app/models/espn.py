"""Schemas for an imported ESPN league."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.league import LeagueSettings


class ImportedPlayer(BaseModel):
    espn_id: int
    name: str
    position: str = Field(description="QB/RB/WR/TE, or K/DST/OTHER (not modeled).")
    nfl_team: str | None
    lineup_slot: str
    player_id: str | None = Field(description="Matched Fleece Detector id, or None if unmatched.")
    match_method: Literal["espn_id", "name_position", "name"] | None


class ImportedTeam(BaseModel):
    team_id: int
    name: str
    abbrev: str
    players: list[ImportedPlayer]
    player_ids: list[str] = Field(description="Matched ids, ready to use as a roster.")


class LeagueImport(BaseModel):
    league_id: int
    season: int
    name: str
    size: int
    current_week: int | None
    league_settings: LeagueSettings = Field(description="ESPN settings converted to Fleece Detector settings.")
    scoring_summary: list[str]
    teams: list[ImportedTeam]
    matched_count: int
    unmatched: list[str] = Field(description="Skill players we couldn't match to projections (name, position).")
    unsupported_count: int = Field(description="Kickers and defenses on rosters (not modeled).")
    notes: list[str]
    fetched_at: str
