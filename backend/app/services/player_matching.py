"""Match players from another source (ESPN) to our player ids.

1. By ESPN id, when our data has it (Sleeper provides it for only ~25% of players).
2. By normalized name + position: "D.J. Moore" == "DJ Moore", "Kenneth Walker III" == "Kenneth Walker".
3. By normalized name alone, but only if exactly one of our players has that name.

Anything else is reported as unmatched rather than guessed.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from app.models.player import Player

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

MatchMethod = Literal["espn_id", "name_position", "name"]


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9\s-]", "", ascii_name.lower()).replace("-", " ").split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


class PlayerMatcher:
    def __init__(self, players: list[Player]) -> None:
        self._by_espn: dict[int, str] = {p.espn_id: p.player_id for p in players if p.espn_id is not None}
        self._by_name_pos: dict[tuple[str, str], list[str]] = {}
        self._by_name: dict[str, list[str]] = {}
        for p in players:
            key = normalize_name(p.name)
            self._by_name_pos.setdefault((key, p.position.value), []).append(p.player_id)
            self._by_name.setdefault(key, []).append(p.player_id)

    def match(self, espn_id: int | None, name: str, position: str) -> tuple[str | None, MatchMethod | None]:
        if espn_id is not None and espn_id in self._by_espn:
            return self._by_espn[espn_id], "espn_id"
        key = normalize_name(name)
        candidates = self._by_name_pos.get((key, position), [])
        if len(candidates) == 1:
            return candidates[0], "name_position"
        if not candidates and len(self._by_name.get(key, [])) == 1:
            return self._by_name[key][0], "name"
        return None, None
