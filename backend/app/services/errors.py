"""Domain errors, translated into HTTP responses in app/main.py."""

from __future__ import annotations


class UnknownPlayerError(LookupError):
    def __init__(self, player_ids: list[str]) -> None:
        self.player_ids = player_ids
        super().__init__(f"Unknown player id(s): {', '.join(player_ids)}")


class TradeValidationError(ValueError):
    """The trade request is well-formed JSON but describes an impossible trade."""
