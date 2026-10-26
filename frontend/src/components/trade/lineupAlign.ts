import type { LineupSlotAssignment } from "../../types/api";

export interface SlotRow {
  slot: string;
  before?: LineupSlotAssignment;
  after?: LineupSlotAssignment;
}

/**
 * Pair the before/after starting lineups for display, slot type by slot type.
 *
 * Players who start at the same slot type both times stay on their own row, even if they moved
 * from RB1 to RB2; only players who left are paired with players who arrived. So trading
 * Walker for Gibbs reads "RB: Walker -> Gibbs", not "Walker -> Williams" + "Williams -> Gibbs".
 */
export function alignBySlot(before: LineupSlotAssignment[], after: LineupSlotAssignment[]): SlotRow[] {
  const rows: SlotRow[] = [];
  for (const slot of [...new Set([...before, ...after].map((s) => s.slot))]) {
    const b = before.filter((s) => s.slot === slot);
    const a = after.filter((s) => s.slot === slot);
    const afterIds = new Set(a.map((s) => s.player_id));
    const beforeIds = new Set(b.map((s) => s.player_id));
    for (const s of b) if (afterIds.has(s.player_id)) rows.push({ slot, before: s, after: s });
    const out = b.filter((s) => !afterIds.has(s.player_id));
    const into = a.filter((s) => !beforeIds.has(s.player_id));
    for (let i = 0; i < Math.max(out.length, into.length); i++) rows.push({ slot, before: out[i], after: into[i] });
  }
  return rows;
}
