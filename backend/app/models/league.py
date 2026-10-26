"""League configuration: positions, lineup slots, and scoring rules."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"


# Which positions may fill each starting slot. FLEX and SUPERFLEX overlap with the
# dedicated slots, which is why lineup selection is solved as an assignment problem.
SLOT_ELIGIBILITY: dict[str, frozenset[Position]] = {
    "QB": frozenset({Position.QB}),
    "RB": frozenset({Position.RB}),
    "WR": frozenset({Position.WR}),
    "TE": frozenset({Position.TE}),
    "FLEX": frozenset({Position.RB, Position.WR, Position.TE}),
    "SUPERFLEX": frozenset({Position.QB, Position.RB, Position.WR, Position.TE}),
}

# Fixed slot order keeps lineup output deterministic and readable.
SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX"]

# Upper bound for each slot count (also mirrored in frontend/src/types/api.ts).
SLOT_MAX = {"QB": 3, "RB": 4, "WR": 5, "TE": 3, "FLEX": 3, "SUPERFLEX": 2, "BENCH": 12}


class LineupSlots(BaseModel):
    """Starting lineup requirements plus bench size (ESPN-style)."""

    QB: int = Field(1, ge=0, le=SLOT_MAX["QB"])
    RB: int = Field(2, ge=0, le=SLOT_MAX["RB"])
    WR: int = Field(2, ge=0, le=SLOT_MAX["WR"])
    TE: int = Field(1, ge=0, le=SLOT_MAX["TE"])
    FLEX: int = Field(1, ge=0, le=SLOT_MAX["FLEX"])
    SUPERFLEX: int = Field(0, ge=0, le=SLOT_MAX["SUPERFLEX"])
    BENCH: int = Field(7, ge=0, le=SLOT_MAX["BENCH"])  # ESPN default (K and D/ST are not modeled yet)

    def starting_slots(self) -> list[str]:
        """Expanded slot list, e.g. ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]."""
        return [slot for slot in SLOT_ORDER for _ in range(getattr(self, slot))]

    @property
    def num_starters(self) -> int:
        return len(self.starting_slots())

    @property
    def max_roster_size(self) -> int:
        return self.num_starters + self.BENCH

    @model_validator(mode="after")
    def _at_least_one_starter(self) -> "LineupSlots":
        if self.num_starters == 0:
            raise ValueError("Lineup must contain at least one starting slot.")
        return self


class ScoringSettings(BaseModel):
    """Fantasy points awarded per unit of each stat."""

    pass_yd: float = 0.04
    pass_td: float = 4.0
    pass_int: float = -2.0
    rush_yd: float = 0.1
    rush_td: float = 6.0
    reception: float = 1.0
    rec_yd: float = 0.1
    rec_td: float = 6.0
    fumble_lost: float = -2.0
    two_pt_conversion: float = 2.0
    te_reception_bonus: float = 0.0  # "TE premium" leagues award extra points per TE catch


SCORING_PRESETS: dict[str, ScoringSettings] = {
    "ppr": ScoringSettings(reception=1.0),
    "half_ppr": ScoringSettings(reception=0.5),
    "standard": ScoringSettings(reception=0.0),
}

ScoringFormat = Literal["ppr", "half_ppr", "standard", "custom"]


class LeagueSettings(BaseModel):
    num_teams: int = Field(12, ge=4, le=20)
    scoring_format: ScoringFormat = "ppr"
    scoring: ScoringSettings | None = Field(
        None, description="Required when scoring_format is 'custom'; ignored otherwise."
    )
    lineup: LineupSlots = Field(default_factory=LineupSlots)

    @model_validator(mode="after")
    def _custom_requires_scoring(self) -> "LeagueSettings":
        if self.scoring_format == "custom" and self.scoring is None:
            raise ValueError("scoring must be provided when scoring_format is 'custom'.")
        return self

    def resolved_scoring(self) -> ScoringSettings:
        if self.scoring_format == "custom":
            assert self.scoring is not None
            return self.scoring
        return SCORING_PRESETS[self.scoring_format]

    def cache_key(self) -> str:
        """Stable key for caching league-dependent valuations."""
        return self.model_copy(update={"scoring": self.resolved_scoring()}).model_dump_json()
