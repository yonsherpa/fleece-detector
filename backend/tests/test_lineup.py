from app.models.league import LineupSlots, Position
from app.services.lineup import RosterEntry, optimize_lineup


def e(pid: str, pos: str, pts: float) -> RosterEntry:
    return RosterEntry(pid, pid, Position(pos), pts)


def test_flex_is_solved_optimally_where_greedy_fails():
    # Filling slots in order (FLEX first) would put WR1 in FLEX and WR2 in WR = 25.
    # Optimal: WR1 in WR, RB1 in FLEX = 35.
    roster = [e("WR1", "WR", 20), e("WR2", "WR", 5), e("RB1", "RB", 15)]
    lineup = optimize_lineup(roster, ["FLEX", "WR"])
    assert lineup.total_points == 35
    assert dict(lineup.starters) == {"FLEX": roster[2], "WR": roster[0]}
    assert [b.player_id for b in lineup.bench] == ["WR2"]


def test_no_player_fills_two_slots():
    roster = [e("RB1", "RB", 30), e("WR1", "WR", 1)]
    lineup = optimize_lineup(roster, ["RB", "FLEX", "WR"])
    ids = [p.player_id for _, p in lineup.starters]
    assert len(ids) == len(set(ids))
    assert lineup.total_points == 31


def test_slot_left_empty_when_no_eligible_player():
    roster = [e("QB1", "QB", 20), e("WR1", "WR", 10)]
    lineup = optimize_lineup(roster, LineupSlots().starting_slots())
    assert {slot for slot, _ in lineup.starters} == {"QB", "WR"}
    assert lineup.total_points == 30


def test_superflex_starts_second_qb_when_best():
    roster = [e("QB1", "QB", 25), e("QB2", "QB", 22), e("RB1", "RB", 10), e("RB2", "RB", 9)]
    lineup = optimize_lineup(roster, ["QB", "RB", "SUPERFLEX"])
    assert dict(lineup.starters)["SUPERFLEX"].player_id == "QB2"
    assert lineup.total_points == 57


def test_result_is_independent_of_input_order():
    roster = [e("A", "RB", 10), e("B", "RB", 10), e("C", "WR", 10), e("D", "TE", 10)]
    first = optimize_lineup(roster, ["RB", "FLEX"])
    second = optimize_lineup(list(reversed(roster)), ["RB", "FLEX"])
    assert first == second
