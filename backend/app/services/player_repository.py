"""In-memory player store plus cached, league-specific valuations."""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

from app.config import SNAPSHOT_DIR, Settings
from app.data.projection_provider import CsvProjectionProvider, DataSourceError, ProjectionProvider
from app.models.league import LeagueSettings, Position
from app.models.player import DatasetInfo, Player, PlayerValue
from app.services.errors import UnknownPlayerError
from app.services.valuation import Valuation, build_valuation

logger = logging.getLogger(__name__)

_MAX_CACHED_VALUATIONS = 32


class PlayerRepository:
    def __init__(self, players: list[Player], dataset: DatasetInfo) -> None:
        self._players = {p.player_id: p for p in players}
        self.dataset = dataset
        self._valuations: OrderedDict[str, Valuation] = OrderedDict()

    @classmethod
    def from_provider(cls, provider: ProjectionProvider) -> "PlayerRepository":
        players, dataset = provider.load()
        return cls(players, dataset)

    def all_players(self) -> list[Player]:
        return list(self._players.values())

    def __len__(self) -> int:
        return len(self._players)

    def get(self, player_id: str) -> Player:
        try:
            return self._players[player_id]
        except KeyError:
            raise UnknownPlayerError([player_id]) from None

    def require_known(self, player_ids: list[str]) -> None:
        unknown = [pid for pid in player_ids if pid not in self._players]
        if unknown:
            raise UnknownPlayerError(sorted(set(unknown)))

    def valuation(self, league: LeagueSettings) -> Valuation:
        key = league.cache_key()
        if key in self._valuations:
            self._valuations.move_to_end(key)
            return self._valuations[key]
        valuation = build_valuation(list(self._players.values()), league)
        self._valuations[key] = valuation
        if len(self._valuations) > _MAX_CACHED_VALUATIONS:
            self._valuations.popitem(last=False)
        return valuation

    def search(
        self,
        league: LeagueSettings,
        query: str | None = None,
        position: Position | None = None,
        limit: int = 50,
        ids: list[str] | None = None,
    ) -> tuple[list[PlayerValue], int]:
        """Players matching name/team (or an explicit id list), best value first. Returns (page, total)."""
        all_values = self.valuation(league).values
        values = [all_values[i] for i in dict.fromkeys(ids) if i in all_values] if ids is not None else all_values.values()
        q = (query or "").strip().lower()
        # Typing a position ("rb") means "show RBs", not "names containing r-b" (e.g. "Corbin").
        if q.upper() in Position.__members__:
            position = position or Position(q.upper())
            q = ""
        matches = [
            v
            for v in values
            if (position is None or v.position == position)
            and (not q or q in v.name.lower() or q == v.nfl_team.lower())
        ]
        matches.sort(key=lambda v: (-v.value_over_replacement, -v.projected_ros_points, v.name))
        return matches[:limit], len(matches)


def _snapshot_provider() -> CsvProjectionProvider:
    return CsvProjectionProvider(SNAPSHOT_DIR / "players.csv", SNAPSHOT_DIR / "metadata.json")


def create_repository(settings: Settings) -> PlayerRepository:
    """Load the configured data source, falling back to the last saved real-data snapshot."""
    if settings.data_source != "snapshot":
        csv_path = Path(settings.data_source)
        provider = CsvProjectionProvider(csv_path, csv_path.with_name("metadata.json"))
        try:
            return PlayerRepository.from_provider(provider)
        except DataSourceError:
            logger.exception("Configured data source failed; falling back to the saved snapshot.")
    try:
        return PlayerRepository.from_provider(_snapshot_provider())
    except DataSourceError as exc:
        raise DataSourceError(
            f"{exc}. No player data available: run `python scripts/update_data.py` from backend/."
        ) from exc
