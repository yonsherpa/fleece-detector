"""Runtime configuration read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshot"  # written by scripts/update_data.py


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("FLEECE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        )
    )
    data_source: str = field(default_factory=lambda: os.getenv("FLEECE_DATA_SOURCE", "snapshot"))


def get_settings() -> Settings:
    return Settings()
