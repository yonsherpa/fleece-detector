"""Roster move suggestions: who to sell, drop, pick up, or trade for.

Everything is measured with the same optimal-lineup engine used for trade grades:

* lineup cost of a player  = best lineup now - best lineup without them
* lineup gain of a player  = best lineup with them - best lineup now
  (if the roster is full, the player whose loss hurts least is dropped first)

Rules (documented in the README):
* Sell high:    value >= 5 and lineup cost <= 25% of value. Others would pay for them; you barely use them.
* Safe to drop: value <= 1 (replacement level) and lineup cost <= 0.5.
* Waiver:       players ranked below num_teams x roster size, i.e. likely unrostered.
* Buy targets:  biggest lineup gains among players worth no more than ~your best sell-high piece.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.league import SLOT_ELIGIBILITY, LeagueSettings
from app.models.moves import MoveSuggestion, MovesRequest, MovesResponse, TrendingInfo
from app.models.player import PlayerValue
from app.services.errors import TradeValidationError
from app.services.lineup import OptimalLineup, RosterEntry, optimize_lineup
from app.services.player_repository import PlayerRepository
from app.services.roster import enforce_max_size, roster_entry
from app.services.trending import LOOKBACK_HOURS, TrendingService
from app.services.valuation import Valuation

SELL_MIN_VALUE = 5.0
SELL_MAX_COST_SHARE = 0.25
DROP_MAX_VALUE = 1.0
DROP_MAX_COST = 0.5
BUY_BUDGET_SLACK = 1.10
LIST_LIMIT = 6
WAIVER_CANDIDATES = 60


@dataclass
class _Team:
    entries: list[RosterEntry]
    slots: list[str]
    max_size: int
    lineup: OptimalLineup

    @property
    def base(self) -> float:
        return self.lineup.total_points

    @classmethod
    def build(cls, ids: list[str], valuation: Valuation, league: LeagueSettings) -> "_Team":
        entries = [roster_entry(pid, valuation) for pid in ids]
        slots = league.lineup.starting_slots()
        return cls(entries, slots, league.lineup.max_roster_size, optimize_lineup(entries, slots))

    def cost_if_removed(self, entry: RosterEntry) -> float:
        others = [e for e in self.entries if e is not entry]
        return round(self.base - optimize_lineup(others, self.slots).total_points, 1)

    def gain_if_added(self, entry: RosterEntry) -> tuple[float, str | None]:
        if not self._could_start(entry):
            return 0.0, None
        candidates = [*self.entries, entry]
        dropped_name = None
        if len(candidates) > self.max_size:
            candidates, dropped = enforce_max_size(candidates, self.slots, self.max_size)
            if any(d is entry for d in dropped):
                return 0.0, None
            dropped_name = dropped[0].name if dropped else None
        gain = optimize_lineup(candidates, self.slots).total_points - self.base
        return round(max(gain, 0.0), 1), dropped_name

    def _could_start(self, entry: RosterEntry) -> bool:
        """Cheap pre-check: a newcomer can only help by beating a starter in a slot they're eligible for."""
        if len(self.lineup.starters) < len(self.slots):
            return True  # an empty slot: anyone eligible helps
        eligible = [e.points for slot, e in self.lineup.starters if entry.position in SLOT_ELIGIBILITY[slot]]
        return bool(eligible) and entry.points > min(eligible)


def _suggestion(p: PlayerValue, reason: str, **extra) -> MoveSuggestion:
    return MoveSuggestion(player=p, reason=reason, **extra)


def build_moves(req: MovesRequest, repo: PlayerRepository, trending: TrendingService) -> MovesResponse:
    league = req.league
    valuation = repo.valuation(league)
    values = valuation.values

    # Roster: de-duplicate, skip ids the dataset no longer knows (the UI flags those separately).
    roster_ids = [pid for pid in dict.fromkeys(req.roster or []) if pid in values]
    if len(roster_ids) > league.lineup.max_roster_size:
        raise TradeValidationError(
            f"Roster has {len(roster_ids)} players; league maximum is {league.lineup.max_roster_size}."
        )
    team = _Team.build(roster_ids, valuation, league) if roster_ids else None
    on_roster = set(roster_ids)
    notes: list[str] = []

    # Who owns whom in the league (other teams only). Known only with imported league rosters.
    owner_of: dict[str, str] = {}
    for other in req.league_rosters or []:
        for pid in other.player_ids:
            if pid not in on_roster:
                owner_of.setdefault(pid, other.team_name)
    league_known = req.league_rosters is not None

    sell_high: list[MoveSuggestion] = []
    safe_to_drop: list[MoveSuggestion] = []
    if team:
        for entry in team.entries:
            p = values[entry.player_id]
            cost = team.cost_if_removed(entry)
            vor = p.value_over_replacement
            if vor >= SELL_MIN_VALUE and cost <= SELL_MAX_COST_SHARE * vor:
                sell_high.append(
                    _suggestion(
                        p,
                        f"Worth {vor:.1f} in trade value to other teams, but trading this player costs your best "
                        f"lineup only {cost:.1f} points.",
                        lineup_change=-cost or 0.0,  # avoid "-0.0"
                    )
                )
            elif vor <= DROP_MAX_VALUE and cost <= DROP_MAX_COST:
                safe_to_drop.append(
                    _suggestion(
                        p,
                        f"Projected {p.projected_ros_points:.0f} rest-of-season points, at or below replacement "
                        "level, and not in your best lineup.",
                        lineup_change=-cost or 0.0,  # avoid "-0.0"
                    )
                )
        sell_high.sort(key=lambda s: -s.player.value_over_replacement)
        safe_to_drop.sort(key=lambda s: s.player.projected_ros_points)
    else:
        notes.append(
            "Add your roster to unlock Sell high, Safe to drop and Buy targets, and to see how each player "
            "would change your lineup."
        )

    def gain_fields(p: PlayerValue) -> dict:
        if not team:
            return {}
        gain, dropped = team.gain_if_added(roster_entry(p.player_id, valuation))
        return {"lineup_change": gain, "drop_to_make_room": dropped}

    # Trending (live from Sleeper).
    snap = trending.get()
    trending_adds: list[MoveSuggestion] = []
    trending_drops: list[MoveSuggestion] = []
    unprojected = 0
    for kind, items, out in (("add", snap.adds, trending_adds), ("drop", snap.drops, trending_drops)):
        for item in items:
            pid = f"sleeper-{item['player_id']}"
            p = values.get(pid)
            if p is None:
                unprojected += kind == "add"
                continue
            count = int(item.get("count", 0))
            if kind == "add":
                extra = gain_fields(p) if pid not in on_roster else {}
                reason = f"Added in {count:,} Sleeper leagues in the last {LOOKBACK_HOURS} hours."
            else:
                extra = {}
                reason = f"Dropped in {count:,} Sleeper leagues in the last {LOOKBACK_HOURS} hours."
            if pid in owner_of:
                reason += f" Already on {owner_of[pid]} in your league."
            out.append(
                _suggestion(
                    p, reason, trend_count=count, on_your_roster=pid in on_roster, owner_team=owner_of.get(pid), **extra
                )
            )
        del out[10:]
    trending_info = TrendingInfo(
        available=snap.error is None,
        message=snap.error,
        lookback_hours=LOOKBACK_HOURS,
        fetched_at=snap.fetched_at,
        unprojected_count=unprojected,
    )

    # Waiver targets. With league rosters: real free agents (on nobody's team). Without: estimated as
    # players ranked below what the league can roster.
    cutoff = league.num_teams * league.lineup.max_roster_size
    ranked = sorted(
        (v for v in values.values() if v.projection_available),
        key=lambda v: (-v.projected_ros_points, v.player_id),
    )
    rank_of = {v.player_id: i + 1 for i, v in enumerate(ranked)}
    if league_known:
        pool = [v for v in ranked if v.player_id not in on_roster and v.player_id not in owner_of]
    else:
        pool = [v for v in ranked[cutoff:] if v.player_id not in on_roster]
    pool = pool[:WAIVER_CANDIDATES]
    available = "Free agent in your league" if league_known else "Likely available"
    waiver: list[MoveSuggestion] = []
    for p in pool:
        extra = gain_fields(p)
        if team and extra["lineup_change"] > 0:
            reason = f"{available}. Would add {extra['lineup_change']:.1f} points to your best lineup."
        elif team:
            reason = f"{available}, but doesn't beat your current starters."
        elif league_known:
            reason = f"Free agent in your league, ranked #{rank_of[p.player_id]} overall."
        else:
            reason = (
                f"Ranked #{rank_of[p.player_id]} overall, outside the ~{cutoff} players a "
                f"{league.num_teams}-team league usually rosters."
            )
        waiver.append(_suggestion(p, reason, **extra))
    waiver.sort(key=lambda s: (-(s.lineup_change or 0), -s.player.projected_ros_points))
    del waiver[LIST_LIMIT:]
    if team and waiver and all((s.lineup_change or 0) <= 0 for s in waiver):
        notes.append(
            f"No {'free agent in your league' if league_known else 'likely free agent'} beats your current "
            "starters. Waiver adds would only be depth."
        )

    # Buy targets: what your surplus could realistically get you. With league rosters, only players
    # another team actually owns (free agents are waiver targets, not trades).
    buy_targets: list[MoveSuggestion] = []
    budget = max((s.player.value_over_replacement for s in sell_high), default=None)
    if team:
        for p in ranked:
            if p.player_id in on_roster or (league_known and p.player_id not in owner_of):
                continue
            if budget is not None and p.value_over_replacement > budget * BUY_BUDGET_SLACK:
                continue
            extra = gain_fields(p)
            if extra["lineup_change"] <= 0:
                continue
            owner = owner_of.get(p.player_id)
            buy_targets.append(
                _suggestion(
                    p,
                    f"Would add {extra['lineup_change']:.1f} points to your best lineup; trade value "
                    f"{p.value_over_replacement:.1f}." + (f" Owned by {owner}." if owner else ""),
                    owner_team=owner,
                    **extra,
                )
            )
        buy_targets.sort(key=lambda s: (-(s.lineup_change or 0), s.player.value_over_replacement))
        del buy_targets[LIST_LIMIT:]
        if budget is None:
            notes.append("You have no clear surplus to sell, so buy targets aren't limited by budget.")

    return MovesResponse(
        has_roster=team is not None,
        sell_high=sell_high[:LIST_LIMIT],
        safe_to_drop=safe_to_drop[:LIST_LIMIT],
        trending_adds=trending_adds,
        trending_drops=trending_drops,
        waiver_targets=waiver,
        buy_targets=buy_targets,
        buy_budget=round(budget, 1) if budget is not None else None,
        rostered_cutoff=cutoff,
        availability="league" if league_known else "estimated",
        trending=trending_info,
        notes=notes,
        league=league,
        dataset=repo.dataset,
    )
