import { ArrowRight, Info } from "lucide-react";
import { useState } from "react";
import type { LineupSlotAssignment, TeamImpact, TradeEvaluation } from "../../types/api";
import { cx, signed } from "../ui";
import { alignBySlot } from "./lineupAlign";

const SLOT_LABEL: Record<string, string> = { SUPERFLEX: "SFLX" };

/** "Trevor Lawrence" -> "T. Lawrence"; keeps suffixes like "Walker III". */
function shortName(name: string): string {
  const [first, ...rest] = name.split(" ");
  return rest.length ? `${first[0]}. ${rest.join(" ")}` : name;
}

function Cell({ s, changed, side }: { s?: LineupSlotAssignment; changed: boolean; side: "before" | "after" }) {
  if (!s) return <span className="text-xs text-ink-500">Empty</span>;
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-2">
      <span
        className={cx(
          "truncate text-sm",
          s.is_replacement && "italic",
          changed ? (side === "after" ? "font-medium text-mint-400" : "text-ink-500 line-through decoration-ink-600") : "text-ink-200",
        )}
        title={s.is_replacement ? "Assumed waiver pickup for a roster spot the trade opened" : s.name}
      >
        <span className="sm:hidden">{s.is_replacement ? s.name : shortName(s.name)}</span>
        <span className="hidden sm:inline">{s.name}</span>
      </span>
      <span className="num shrink-0 text-xs text-ink-400">{s.projected_ros_points.toFixed(0)}</span>
    </div>
  );
}

function TeamLineup({ team }: { team: TeamImpact }) {
  const r = team.roster!;
  const rows = alignBySlot(r.lineup_before.starters, r.lineup_after.starters);
  return (
    <div>
      <div className="overflow-hidden rounded-md border border-ink-700">
        <div className="grid grid-cols-[2.25rem_1fr_1fr] sm:grid-cols-[3.5rem_1fr_1.25rem_1fr] items-center gap-2 border-b border-ink-700 bg-ink-850 px-2 py-2 sm:px-3">
          <span className="label">Slot</span>
          <span className="label">Before</span>
          <span className="hidden sm:block" />
          <span className="label">After</span>
        </div>
        {rows.map((row, i) => {
          const changed = row.before?.player_id !== row.after?.player_id;
          return (
            <div
              key={i}
              className={cx(
                "grid grid-cols-[2.25rem_1fr_1fr] sm:grid-cols-[3.5rem_1fr_1.25rem_1fr] items-center gap-2 border-b border-ink-700/60 px-2 py-2 last:border-b-0 sm:px-3",
                changed && "bg-mint-500/[0.06]",
              )}
            >
              <span className="font-mono text-[11px] font-semibold text-ink-400">{SLOT_LABEL[row.slot] ?? row.slot}</span>
              <Cell s={row.before} changed={changed} side="before" />
              <ArrowRight className={cx("hidden h-3.5 w-3.5 sm:block", changed ? "text-mint-400" : "text-ink-700")} />
              <Cell s={row.after} changed={changed} side="after" />
            </div>
          );
        })}
        <div className="grid grid-cols-[2.25rem_1fr_1fr] sm:grid-cols-[3.5rem_1fr_1.25rem_1fr] items-center gap-2 bg-ink-850/60 px-2 py-2.5 text-sm sm:px-3">
          <span className="label">Total</span>
          <span className="num text-ink-300">{r.lineup_before.total_points.toFixed(0)}</span>
          <span className="hidden sm:block" />
          <span className="flex items-baseline justify-between">
            <span className="num font-semibold text-ink-100">{r.lineup_after.total_points.toFixed(0)}</span>
            <span className={cx("num text-xs font-semibold", r.lineup_delta >= 0 ? "text-mint-400" : "text-flag-400")}>
              {signed(r.lineup_delta)}
            </span>
          </span>
        </div>
      </div>

      {(r.dropped_players.length > 0 || r.replacements_added.length > 0) && (
        <div className="mt-3 space-y-1.5 text-xs text-ink-400">
          {r.dropped_players.length > 0 && (
            <p>
              <span className="text-ink-200">Roster limit:</span> would drop {r.dropped_players.join(", ")}.
            </p>
          )}
          {r.replacements_added.length > 0 && (
            <p className="flex gap-1.5">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                The trade opens {r.replacements_added.length} roster spot(s), assumed filled from waivers (
                {r.replacements_added.join(", ")}) at the level of the best player most leagues leave unrostered.
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Before/after optimal starting lineups for each team whose roster was entered. */
export function LineupComparison({ result }: { result: TradeEvaluation }) {
  const teams = (
    [
      ["Team A (you)", result.team_a],
      ["Team B", result.team_b],
    ] as const
  ).filter(([, t]) => t.roster);
  const [active, setActive] = useState(0);
  if (teams.length === 0) return null;
  const [, team] = teams[Math.min(active, teams.length - 1)];

  return (
    <div className="card animate-rise p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Starting lineup: before vs after</h3>
          <p className="mt-0.5 text-xs text-ink-400">
            Best possible lineup each way, using projected rest-of-season points. Changed slots are highlighted.
          </p>
        </div>
        {teams.length > 1 && (
          <div className="flex rounded-lg border border-ink-700 bg-ink-900 p-0.5" role="tablist">
            {teams.map(([label], i) => (
              <button
                key={label}
                role="tab"
                aria-selected={i === active}
                onClick={() => setActive(i)}
                className={cx(
                  "rounded-md px-2.5 py-1 text-xs font-semibold",
                  i === active ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-100",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      <TeamLineup team={team} />
    </div>
  );
}
