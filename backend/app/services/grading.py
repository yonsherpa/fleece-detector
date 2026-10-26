"""Stage 3: transparent conversion of calculated impact into letter grades.

Two scores, two tables (documented in the README):

* roster_aware -- % change in the team's projected optimal starting lineup
  (rest of season). Used when we know the team's roster.
* value_only  -- net value over replacement as % of the larger side:
  (received - given) / max(received, given) x 100. Used without a roster.

Grades are per team. Fairness is separate: it only asks whether both sides
exchanged similar value, not whether the trade helps either team.
"""

from __future__ import annotations

import math
from typing import Literal

# (minimum score, grade), checked top to bottom. Around 0 is "C+/C" = neutral.
ROSTER_AWARE_THRESHOLDS: list[tuple[float, str]] = [
    (6.0, "A+"), (4.5, "A"), (3.0, "A-"),
    (2.0, "B+"), (1.25, "B"), (0.5, "B-"),
    (0.0, "C+"), (-0.5, "C"), (-1.25, "C-"),
    (-2.0, "D+"), (-3.0, "D"), (-4.5, "D-"),
]
# Aligned with the fairness labels: losing <=10% of value (fairness >= 90, "very fair") stays in
# the C range, "fair" (80-90) maps to D+/D, "uneven" (65-80) to D-, and only "lopsided" (< 65) is F.
VALUE_ONLY_THRESHOLDS: list[tuple[float, str]] = [
    (35.0, "A+"), (25.0, "A"), (20.0, "A-"),
    (15.0, "B+"), (10.0, "B"), (5.0, "B-"),
    (0.0, "C+"), (-5.0, "C"), (-10.0, "C-"),
    (-15.0, "D+"), (-20.0, "D"), (-35.0, "D-"),
]

FAIR_EVEN_THRESHOLD = 95.0       # fairness score at/above which neither side is "favored"
WINNER_EVEN_THRESHOLD_PCT = 0.5  # lineup % gap below which the trade is a wash


def letter_grade(score: float, method: Literal["roster_aware", "value_only"]) -> str:
    table = ROSTER_AWARE_THRESHOLDS if method == "roster_aware" else VALUE_ONLY_THRESHOLDS
    score = round(score, 2)  # avoid float noise flipping a boundary
    for minimum, grade in table:
        if score >= minimum:
            return grade
    return "F"


def value_only_score(value_received: float, value_given: float) -> float:
    larger = max(value_received, value_given)
    if larger <= 0:
        return 0.0
    return round(100 * (value_received - value_given) / larger, 2)


def fairness(value_a_receives: float, value_b_receives: float) -> tuple[float, str, str]:
    """Return (score 0-100, label, favored side) from the value each side receives."""
    larger = max(value_a_receives, value_b_receives)
    # Whole number, rounded half-up here so every client shows the same value
    # (Python and JavaScript round 84.5 differently).
    raw = 100.0 if larger <= 0 else 100 * min(value_a_receives, value_b_receives) / larger
    score = float(math.floor(raw + 0.5))

    if score >= 90:
        label = "Very fair"
    elif score >= 80:
        label = "Fair"
    elif score >= 65:
        label = "Uneven"
    else:
        label = "Lopsided"

    if score >= FAIR_EVEN_THRESHOLD:
        favored = "even"
    else:
        favored = "team_a" if value_a_receives > value_b_receives else "team_b"
    return score, label, favored
