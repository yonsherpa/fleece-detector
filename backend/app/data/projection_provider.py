"""Projection providers: where player projections come from.

The rest of the app only depends on the `ProjectionProvider` protocol, so swapping
the bundled CSV for an nflverse-derived dataset or a trained ML model is a matter
of adding a new provider class -- the valuation and trade logic do not change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.models.player import DatasetInfo, Player, PlayerProjection

REQUIRED_COLUMNS = {"player_id", "name", "position", "nfl_team", "games_remaining"}
STAT_COLUMNS = list(PlayerProjection.model_fields)


class DataSourceError(RuntimeError):
    """Raised when a projection source cannot be read or is malformed."""


class ProjectionProvider(Protocol):
    def load(self) -> tuple[list[Player], DatasetInfo]: ...


def _clean(value: object) -> object | None:
    return None if pd.isna(value) else value


class CsvProjectionProvider:
    """Loads per-game projections from a CSV plus a metadata.json describing the source."""

    def __init__(self, csv_path: Path, metadata_path: Path | None = None) -> None:
        self.csv_path = csv_path
        self.metadata_path = metadata_path

    def load(self) -> tuple[list[Player], DatasetInfo]:
        try:
            df = pd.read_csv(self.csv_path, dtype={"player_id": str})
        except (OSError, pd.errors.ParserError) as exc:
            raise DataSourceError(f"Could not read projections from {self.csv_path}: {exc}") from exc

        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise DataSourceError(f"Projection CSV is missing columns: {sorted(missing)}")
        if df["player_id"].duplicated().any():
            dupes = df.loc[df["player_id"].duplicated(), "player_id"].tolist()
            raise DataSourceError(f"Duplicate player_id values in projections: {dupes[:5]}")

        players = [self._row_to_player(row) for row in df.to_dict(orient="records")]
        return players, self._load_metadata()

    @staticmethod
    def _row_to_player(row: dict) -> Player:
        stats = {col: row.get(col) for col in STAT_COLUMNS if col in row}
        # A row with no stat values at all means "no projection", which is different
        # from "projected for zero" -- keep that distinction explicit.
        has_projection = any(not pd.isna(v) for v in stats.values())
        projection = (
            PlayerProjection(**{k: (0.0 if pd.isna(v) else float(v)) for k, v in stats.items()})
            if has_projection
            else None
        )
        bye = _clean(row.get("bye_week"))
        espn_id = _clean(row.get("espn_id"))
        gsis_id = _clean(row.get("gsis_id"))
        return Player(
            player_id=str(row["player_id"]),
            name=str(row["name"]),
            position=str(row["position"]).upper(),
            nfl_team=str(row["nfl_team"]),
            bye_week=int(bye) if bye is not None else None,
            games_remaining=int(row["games_remaining"]),
            injury_status=_clean(row.get("injury_status")),
            projection=projection,
            espn_id=int(espn_id) if espn_id is not None else None,
            gsis_id=str(gsis_id) if gsis_id is not None else None,
        )

    def _load_metadata(self) -> DatasetInfo:
        if self.metadata_path and self.metadata_path.exists():
            return DatasetInfo(**json.loads(self.metadata_path.read_text(encoding="utf-8")))
        return DatasetInfo(
            source=self.csv_path.name,
            is_sample=False,
            as_of="unknown",
            description="Projection CSV without a metadata.json; timestamp unknown.",
        )
