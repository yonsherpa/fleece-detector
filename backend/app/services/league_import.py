"""Convert an ESPN league into Fleece Detector settings and rosters."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.integrations import espn
from app.integrations.espn import EspnError, EspnLeague, Fetcher
from app.models.espn import ImportedPlayer, ImportedTeam, LeagueImport
from app.models.league import SCORING_PRESETS, SLOT_MAX, LeagueSettings, LineupSlots, ScoringSettings
from app.services.errors import TradeValidationError
from app.services.player_matching import PlayerMatcher
from app.services.player_repository import PlayerRepository

CACHE_SECONDS = 5 * 60
SKILL = ("QB", "RB", "WR", "TE")

# ESPN scoring statId -> (our ScoringSettings field, yards per point-unit). "Every N yards" rules
# become points per yard (points / N), an approximation of ESPN's whole-increment scoring.
YARDAGE_ITEMS = {
    3: ("pass_yd", 1), 5: ("pass_yd", 5), 6: ("pass_yd", 10), 7: ("pass_yd", 20), 8: ("pass_yd", 25),
    9: ("pass_yd", 50), 10: ("pass_yd", 100),
    24: ("rush_yd", 1), 27: ("rush_yd", 5), 28: ("rush_yd", 10), 29: ("rush_yd", 20), 30: ("rush_yd", 25),
    31: ("rush_yd", 50),
    42: ("rec_yd", 1), 47: ("rec_yd", 5), 48: ("rec_yd", 10), 49: ("rec_yd", 20),
}
DIRECT_ITEMS = {4: "pass_td", 20: "pass_int", 25: "rush_td", 43: "rec_td", 53: "reception", 72: "fumble_lost"}
TWO_POINT_ITEMS = (19, 26, 44)
ALT_RECEPTION_ITEM = 41  # older receptions id; used only if 53 is absent
OFFENSE_STAT_LIMIT = 74  # ids below this are offensive stats; higher ones are kicking/defense


def convert_scoring(items: list[dict]) -> tuple[ScoringSettings, int]:
    """Returns (settings, number of offensive scoring rules we couldn't model)."""
    values = {f: 0.0 for f in ScoringSettings.model_fields}
    by_id = {int(i["statId"]): i for i in items if "statId" in i}
    unmodeled = 0
    two_pt: list[float] = []
    for stat_id, item in by_id.items():
        points = float(item.get("points", 0) or 0)
        if stat_id in YARDAGE_ITEMS:
            field, per = YARDAGE_ITEMS[stat_id]
            values[field] += points / per
        elif stat_id in DIRECT_ITEMS:
            values[DIRECT_ITEMS[stat_id]] = points
            if stat_id == 53:
                te_points = (item.get("pointsOverrides") or {}).get("6")  # override for the TE slot
                if te_points is not None:
                    values["te_reception_bonus"] = float(te_points) - points
        elif stat_id in TWO_POINT_ITEMS:
            two_pt.append(points)
        elif stat_id == ALT_RECEPTION_ITEM and 53 not in by_id:
            values["reception"] = points
        elif stat_id < OFFENSE_STAT_LIMIT and points != 0:
            unmodeled += 1
    if two_pt:
        values["two_pt_conversion"] = sum(two_pt) / len(two_pt)
    return ScoringSettings(**{k: round(v, 4) for k, v in values.items()}), unmodeled


def scoring_format_for(scoring: ScoringSettings) -> str:
    for name, preset in SCORING_PRESETS.items():
        if preset == scoring:
            return name
    return "custom"


def scoring_summary(s: ScoringSettings) -> list[str]:
    ppr = {1.0: "PPR", 0.5: "Half PPR", 0.0: "Standard (no PPR)"}.get(s.reception, f"{s.reception:g} per reception")
    lines = [ppr, f"{s.pass_td:g} per passing TD", f"{s.pass_int:g} per interception"]
    if s.te_reception_bonus:
        lines.append(f"TE premium +{s.te_reception_bonus:g} per catch")
    return lines


def convert_lineup(counts: dict[int, int], team_sizes: list[int]) -> tuple[LineupSlots, list[str]]:
    notes: list[str] = []
    flex = counts.get(espn.SLOT_FLEX, 0) + counts.get(espn.SLOT_RB_WR, 0) + counts.get(espn.SLOT_WR_TE, 0)
    if counts.get(espn.SLOT_RB_WR) or counts.get(espn.SLOT_WR_TE):
        notes.append("RB/WR and WR/TE flex slots are treated as regular FLEX (RB/WR/TE).")
    if counts.get(espn.SLOT_K) or counts.get(espn.SLOT_DST):
        notes.append("Kicker and D/ST slots aren't modeled, so they're left out.")
    wanted = {
        "QB": counts.get(espn.SLOT_QB, 0),
        "RB": counts.get(espn.SLOT_RB, 0),
        "WR": counts.get(espn.SLOT_WR, 0),
        "TE": counts.get(espn.SLOT_TE, 0),
        "FLEX": flex,
        "SUPERFLEX": counts.get(espn.SLOT_OP, 0),
        "BENCH": counts.get(espn.SLOT_BENCH, 0),
    }
    clamped = {}
    for name, count in wanted.items():
        maximum = SLOT_MAX[name]
        clamped[name] = min(count, maximum)
        if count > maximum:
            notes.append(f"ESPN has {count} {name} slots; capped at {maximum}.")
    if sum(v for k, v in clamped.items() if k != "BENCH") == 0:
        clamped["QB"] = 1
        notes.append("No skill-position starting slots found; using 1 QB so the lineup math works.")

    # Rosters can't exceed starters + bench. Kickers/defenses on a bench or roster quirks can push the
    # number of skill players higher, so grow the bench to fit the largest team.
    starters = sum(v for k, v in clamped.items() if k != "BENCH")
    needed_bench = max(team_sizes, default=0) - starters
    if needed_bench > clamped["BENCH"]:
        clamped["BENCH"] = min(needed_bench, SLOT_MAX["BENCH"])
        notes.append(f"Bench raised to {clamped['BENCH']} so every team's skill players fit.")
    return LineupSlots(**clamped), notes


def build_import(league: EspnLeague, repo: PlayerRepository) -> LeagueImport:
    matcher = PlayerMatcher(repo.all_players())
    teams: list[ImportedTeam] = []
    unmatched: list[str] = []
    unsupported = 0
    matched = 0
    for t in league.teams:
        players: list[ImportedPlayer] = []
        ids: list[str] = []
        for p in t.players:
            pid, method = (None, None)
            if p.position in SKILL:
                pid, method = matcher.match(p.espn_id, p.name, p.position)
                if pid:
                    matched += 1
                    if p.lineup_slot != "IR":
                        ids.append(pid)
                else:
                    unmatched.append(f"{p.name} ({p.position})")
            else:
                unsupported += 1
            players.append(
                ImportedPlayer(
                    espn_id=p.espn_id,
                    name=p.name,
                    position=p.position,
                    nfl_team=p.nfl_team,
                    lineup_slot=p.lineup_slot,
                    player_id=pid,
                    match_method=method,
                )
            )
        teams.append(ImportedTeam(team_id=t.team_id, name=t.name, abbrev=t.abbrev, players=players, player_ids=ids))

    lineup, notes = convert_lineup(league.lineup_slot_counts, [len(t.player_ids) for t in teams])
    scoring, unmodeled = convert_scoring(league.scoring_items)
    fmt = scoring_format_for(scoring)
    if unmodeled:
        notes.append(f"{unmodeled} scoring rule(s), such as yardage or long-TD bonuses, aren't modeled.")
    if any(p.lineup_slot == "IR" for t in league.teams for p in t.players):
        notes.append("Players in IR slots are listed but left out of rosters used for grading.")
    if unmatched:
        notes.append(f"{len(unmatched)} player(s) have no projection right now (often injured or deep backups).")

    settings = LeagueSettings(
        num_teams=min(max(league.size, 4), 20),
        scoring_format=fmt,
        scoring=scoring if fmt == "custom" else None,
        lineup=lineup,
    )
    return LeagueImport(
        league_id=league.league_id,
        season=league.season,
        name=league.name,
        size=league.size,
        current_week=league.current_week,
        league_settings=settings,
        scoring_summary=scoring_summary(scoring),
        teams=teams,
        matched_count=matched,
        unmatched=unmatched,
        unsupported_count=unsupported,
        notes=notes,
        fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


class EspnLeagueService:
    """Fetches and parses leagues, with a short cache so repeat visits don't hammer ESPN."""

    def __init__(self, fetcher: Fetcher = espn.fetch_league_json, ttl_seconds: float = CACHE_SECONDS) -> None:
        self._fetcher = fetcher
        self._ttl = ttl_seconds
        self._cache: dict[tuple[int, int], tuple[float, EspnLeague]] = {}

    def get(self, league_id: int, season: int, repo: PlayerRepository) -> LeagueImport:
        if repo.dataset.season is not None and season != repo.dataset.season:
            raise TradeValidationError(
                f"Only the {repo.dataset.season} season can be imported, because projections are for that season."
            )
        key = (league_id, season)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self._ttl:
            league = cached[1]
        else:
            league = espn.parse_league(self._fetcher(league_id, season), league_id, season)
            self._cache[key] = (time.monotonic(), league)
        return build_import(league, repo)


__all__ = ["EspnError", "EspnLeagueService", "build_import", "convert_lineup", "convert_scoring"]
