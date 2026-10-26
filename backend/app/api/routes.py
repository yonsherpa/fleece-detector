"""HTTP endpoints. Kept thin: validation via Pydantic, logic lives in app/services."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import EspnDep, LeagueQueryDep, RepositoryDep, TrendingDep
from app.models.espn import ImportedTeam, LeagueImport
from app.models.league import SCORING_PRESETS, LineupSlots, Position, ScoringSettings
from app.models.moves import MovesRequest, MovesResponse
from app.models.player import DatasetInfo, PlayerListResponse, PlayerValue
from app.models.trade import TradeEvaluation, TradeRequest
from app.services.moves import build_moves
from app.services.trade_evaluator import evaluate_trade

router = APIRouter()


@router.get("/health", tags=["meta"])
def health(repo: RepositoryDep) -> dict:
    return {"status": "ok", "players_loaded": len(repo), "dataset": repo.dataset}


@router.get("/meta", tags=["meta"])
def meta(repo: RepositoryDep) -> dict:
    """Defaults the frontend needs to build league-settings forms."""
    return {
        "scoring_presets": {name: s.model_dump() for name, s in SCORING_PRESETS.items()},
        "custom_scoring_fields": list(ScoringSettings.model_fields),
        "default_lineup": LineupSlots().model_dump(),
        "positions": [p.value for p in Position],
        "dataset": repo.dataset,
    }


@router.get("/players", response_model=PlayerListResponse, tags=["players"])
def list_players(
    repo: RepositoryDep,
    league: LeagueQueryDep,
    q: Annotated[str | None, Query(max_length=60, description="Name or NFL team")] = None,
    position: Position | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ids: Annotated[
        str | None,
        Query(max_length=2000, description="Comma-separated player ids; unknown ids are skipped."),
    ] = None,
) -> PlayerListResponse:
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    players, total = repo.search(league, q, position, limit, ids=id_list)
    return PlayerListResponse(players=players, total=total, dataset=repo.dataset)


@router.get("/players/{player_id}", response_model=PlayerValue, tags=["players"])
def get_player(player_id: str, repo: RepositoryDep, league: LeagueQueryDep) -> PlayerValue:
    repo.get(player_id)  # raises UnknownPlayerError -> 404
    return repo.valuation(league).values[player_id]


@router.post("/trades/evaluate", response_model=TradeEvaluation, tags=["trades"])
def evaluate(req: TradeRequest, repo: RepositoryDep) -> TradeEvaluation:
    return evaluate_trade(req, repo)


@router.post("/moves", response_model=MovesResponse, tags=["moves"])
def moves(req: MovesRequest, repo: RepositoryDep, trending: TrendingDep) -> MovesResponse:
    """Sell, drop, waiver, buy and trending suggestions, measured against your optimal lineup."""
    return build_moves(req, repo, trending)


SeasonQuery = Annotated[int | None, Query(ge=2018, le=2100, description="Defaults to the projections' season.")]


@router.get("/leagues/{league_id}", response_model=LeagueImport, tags=["leagues"])
def get_league(league_id: Annotated[int, Path(ge=1)], repo: RepositoryDep, espn: EspnDep, season: SeasonQuery = None) -> LeagueImport:
    """Import a public ESPN league: settings, scoring, and every team's roster matched to our players."""
    return espn.get(league_id, season or repo.dataset.season or 0, repo)


@router.get("/leagues/{league_id}/teams", response_model=list[ImportedTeam], tags=["leagues"])
def get_league_teams(
    league_id: Annotated[int, Path(ge=1)], repo: RepositoryDep, espn: EspnDep, season: SeasonQuery = None
) -> list[ImportedTeam]:
    return espn.get(league_id, season or repo.dataset.season or 0, repo).teams


@router.get("/dataset", response_model=DatasetInfo, tags=["meta"])
def dataset(repo: RepositoryDep) -> DatasetInfo:
    return repo.dataset
