"""FastAPI dependencies. Tests override `get_repository` to inject fixture data."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request
from pydantic import ValidationError

from app.models.league import LeagueSettings, LineupSlots, ScoringFormat, ScoringSettings
from app.services.league_import import EspnLeagueService
from app.services.player_repository import PlayerRepository
from app.services.trending import TrendingService


def get_espn(request: Request) -> EspnLeagueService:
    return request.app.state.espn


def get_trending(request: Request) -> TrendingService:
    return request.app.state.trending


def get_repository(request: Request) -> PlayerRepository:
    return request.app.state.repository


def parse_lineup(spec: str) -> LineupSlots:
    """Parse "QB:1,RB:2,WR:2,TE:1,FLEX:1,SUPERFLEX:0,BENCH:7" (omitted slots keep defaults)."""
    counts: dict[str, int] = {}
    for part in spec.split(","):
        slot, _, count = part.partition(":")
        slot = slot.strip().upper()
        if slot not in LineupSlots.model_fields or not count.strip().isdigit():
            raise HTTPException(422, detail=f"Invalid lineup entry '{part}'. Expected SLOT:COUNT, e.g. RB:2.")
        counts[slot] = int(count)
    try:
        return LineupSlots(**counts)
    except ValidationError as exc:
        raise HTTPException(422, detail=f"Invalid lineup: {exc.errors()[0]['msg']}") from None


def parse_scoring(spec: str) -> ScoringSettings:
    """Parse "reception:0.5,pass_td:6,te_reception_bonus:0.5" (omitted fields keep defaults)."""
    values: dict[str, float] = {}
    for part in spec.split(","):
        name, _, raw = part.partition(":")
        name = name.strip()
        try:
            values[name] = float(raw)
        except ValueError:
            raise HTTPException(422, detail=f"Invalid scoring entry '{part}'. Expected FIELD:POINTS.") from None
        if name not in ScoringSettings.model_fields:
            raise HTTPException(422, detail=f"Unknown scoring field '{name}'.")
    return ScoringSettings(**values)


def league_from_query(
    scoring_format: Annotated[ScoringFormat, Query()] = "ppr",
    num_teams: Annotated[int, Query(ge=4, le=20)] = 12,
    lineup: Annotated[str | None, Query(max_length=120, description="e.g. QB:1,RB:2,WR:2,TE:1,FLEX:1")] = None,
    scoring: Annotated[
        str | None, Query(max_length=400, description="Custom scoring as FIELD:POINTS pairs (scoring_format=custom).")
    ] = None,
) -> LeagueSettings:
    """League settings for GET endpoints."""
    custom = parse_scoring(scoring) if scoring_format == "custom" and scoring else None
    return LeagueSettings(
        scoring_format=scoring_format if custom else ("ppr" if scoring_format == "custom" else scoring_format),
        num_teams=num_teams,
        scoring=custom,
        lineup=parse_lineup(lineup) if lineup else LineupSlots(),
    )


RepositoryDep = Annotated[PlayerRepository, Depends(get_repository)]
LeagueQueryDep = Annotated[LeagueSettings, Depends(league_from_query)]
TrendingDep = Annotated[TrendingService, Depends(get_trending)]
EspnDep = Annotated[EspnLeagueService, Depends(get_espn)]
