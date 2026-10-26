import { AlertTriangle, Info } from "lucide-react";
import { useState, type ReactNode } from "react";
import { POSITIONS, type LineupSlotAssignment, type TeamImpact, type TradeEvaluation } from "../../types/api";
import { PositionBadge, cx, signed } from "../ui";
import { PlayerValueChart, PositionDeltaChart, type PositionDelta } from "./charts";
import { LineupComparison } from "./LineupComparison";
import { alignBySlot } from "./lineupAlign";

function gradeTone(grade: string): string {
  switch (grade[0]) {
    case "A":
      return "text-mint-500";
    case "B":
      return "text-mint-300";
    case "C":
      return "text-ink-200";
    case "D":
      return "text-amber-400";
    default:
      return "text-flag-400";
  }
}

// The headline is a fixed translation of Team A's letter grade. It adds no new judgment.
const VERDICTS: Record<string, { title: string; body: string }> = {
  A: { title: "You're doing the fleecing", body: "This trade comes out clearly in your favor." },
  B: { title: "Nice pickup", body: "This trade works in your favor." },
  C: { title: "No fleece here", body: "Roughly even for your side." },
  D: { title: "Fleece warning", body: "You're giving up more than you get back." },
  F: { title: "You're getting fleeced", body: "This trade costs you a lot of value." },
};

function scoreCaption(team: TeamImpact): string {
  return team.grade_method === "roster_aware"
    ? `${signed(team.grade_score, 2)}% projected starting lineup`
    : `${signed(team.grade_score)}% net value over replacement`;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2">
      <dt className="text-ink-400">{label}</dt>
      <dd className="min-w-0 text-right text-ink-100">{children}</dd>
    </div>
  );
}

interface SlotChange {
  slot: string;
  before?: LineupSlotAssignment;
  after?: LineupSlotAssignment;
  delta: number;
}

/** Starting slots whose player changes, pairing the k-th RB slot before with the k-th RB slot after. */
function slotChanges(team: TeamImpact): SlotChange[] {
  if (!team.roster) return [];
  const { starters: before } = team.roster.lineup_before;
  const { starters: after } = team.roster.lineup_after;
  return alignBySlot(before, after)
    .filter((row) => row.before?.player_id !== row.after?.player_id)
    .map((row) => ({
      ...row,
      delta: (row.after?.projected_ros_points ?? 0) - (row.before?.projected_ros_points ?? 0),
    }));
}

const lastName = (name?: string) => (name ? name.split(" ").slice(1).join(" ") || name : "Empty");

/** The right-hand summary: grade, verdict and the handful of numbers that decide it. */
export function Verdict({ result }: { result: TradeEvaluation }) {
  const v = VERDICTS[result.grade[0]] ?? VERDICTS.C;
  const a = result.team_a;
  const { score, label, favored } = result.fairness;
  const winner =
    result.winner === "even" ? "Even" : result.winner === "team_a" ? "You (Team A)" : "Team B";
  const changes = slotChanges(a);

  return (
    <div aria-live="polite">
      <div className="flex items-center gap-4 p-4">
        <span className={cx("num text-5xl font-semibold leading-none", gradeTone(result.grade))}>{result.grade}</span>
        <div className="min-w-0">
          <div className="text-base font-semibold text-ink-100">{v.title}</div>
          <div className="text-ink-400">{v.body}</div>
        </div>
      </div>

      <dl className="divide-y divide-ink-700/60 border-t border-ink-700 px-4 text-sm">
        <Row label="Lineup change">
          {a.roster ? (
            <span className="num">
              <span className={a.roster.lineup_delta >= 0 ? "text-mint-400" : "text-flag-400"}>
                {signed(a.roster.lineup_delta)} pts
              </span>{" "}
              <span className="text-ink-400">
                ({a.roster.lineup_before.total_points.toFixed(0)} → {a.roster.lineup_after.total_points.toFixed(0)})
              </span>
            </span>
          ) : (
            <span className="text-ink-500">Add your roster to see this</span>
          )}
        </Row>
        <Row label={a.grade_method === "roster_aware" ? "Grade basis" : "Value change"}>
          <span className="num text-ink-200">{scoreCaption(a)}</span>
        </Row>
        <div className="py-2">
          <div className="flex items-baseline justify-between">
            <dt className="text-ink-400">Fairness</dt>
            <dd className="text-ink-100">
              <span className="num">{score.toFixed(0)}</span> <span className="text-ink-400">· {label}</span>
            </dd>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-700" aria-hidden>
            <div className="h-full rounded-full bg-mint-500" style={{ width: `${score}%` }} />
          </div>
          <p className="mt-1.5 text-xs text-ink-500">
            {favored === "even"
              ? "Balanced value both ways."
              : `More value to ${favored === "team_a" ? "you" : "Team B"}. Fair isn't the same as good for both.`}
          </p>
        </div>
        <Row label="Winner">
          {winner}{" "}
          <span className="text-xs text-ink-500">
            {result.winner_basis === "value_only" ? "· by trade value" : "· by lineup gain"} · Team B gets {result.team_b.grade}
          </span>
        </Row>
      </dl>

      {changes.length > 0 && (
        <div className="border-t border-ink-700 px-4 py-3">
          <div className="label mb-2">Your lineup changes</div>
          <ul className="space-y-1.5">
            {changes.map((c, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className="w-10 shrink-0 font-mono text-[11px] text-ink-500">{c.slot === "SUPERFLEX" ? "SFLX" : c.slot}</span>
                <span className="min-w-0 truncate">
                  <span className="text-ink-500 line-through decoration-ink-600">{lastName(c.before?.name)}</span>
                  <span className="mx-1.5 text-ink-500">→</span>
                  <span className="text-ink-100">{lastName(c.after?.name)}</span>
                </span>
                <span className={cx("num ml-auto shrink-0", c.delta >= 0 ? "text-mint-400" : "text-flag-400")}>
                  {signed(c.delta, 0)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.length > 0 && (
        <ul className="space-y-1.5 border-t border-ink-700 px-4 py-3">
          {result.warnings.map((w) => (
            <li key={w} className="flex gap-2 text-xs text-amber-400">
              {w.includes("SYNTHETIC") ? (
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              )}
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function positionDeltas(result: TradeEvaluation): { data: PositionDelta[]; title: string; unit: string; note: string } {
  const roster = result.team_a.roster;
  if (roster) {
    return {
      data: roster.positions.map((p) => ({ position: p.position, delta: p.starter_points_delta })),
      title: "Starting points by position",
      unit: "starter pts",
      note: "Change in your projected starting points at each position (FLEX counted by player position).",
    };
  }
  const net = Object.fromEntries(POSITIONS.map((p) => [p, 0])) as Record<string, number>;
  result.players_received.forEach((p) => (net[p.position] += p.value_over_replacement));
  result.players_given.forEach((p) => (net[p.position] -= p.value_over_replacement));
  return {
    data: POSITIONS.map((p) => ({ position: p, delta: Math.round(net[p] * 10) / 10 })),
    title: "Net value by position",
    unit: "value over repl.",
    note: "Value over replacement you receive minus what you send, per position.",
  };
}

type Tab = "lineup" | "players" | "positions" | "why";

/** Everything behind the verdict, one tab at a time (Vercel-style tabs). */
export function ResultDetails({ result }: { result: TradeEvaluation }) {
  const hasLineup = !!(result.team_a.roster || result.team_b.roster);
  const [tab, setTab] = useState<Tab>(hasLineup ? "lineup" : "why");
  const pos = positionDeltas(result);
  const strengths = pos.data.filter((d) => d.delta > 0).map((d) => d.position);
  const weaknesses = pos.data.filter((d) => d.delta < 0).map((d) => d.position);
  const tabs: { id: Tab; label: string }[] = [
    { id: "lineup", label: "Lineup" },
    { id: "players", label: "Players" },
    { id: "positions", label: "Positions" },
    { id: "why", label: "Why" },
  ];

  return (
    <section>
      <div role="tablist" className="no-scrollbar flex gap-5 overflow-x-auto overflow-y-hidden border-b border-ink-700">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cx(
              "-mb-px shrink-0 border-b-2 py-2 text-sm transition-colors",
              tab === t.id ? "border-mint-500 text-ink-100" : "border-transparent text-ink-400 hover:text-ink-100",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="pt-4" role="tabpanel">
        {tab === "lineup" &&
          (hasLineup ? (
            <LineupComparison result={result} />
          ) : (
            <p className="card p-4 text-sm text-ink-400">
              Add your roster in the Rosters bar above, and the app will show your best starting lineup before and
              after this trade.
            </p>
          ))}

        {tab === "players" && (
          <div className="card p-4">
            <p className="mb-4 text-sm text-ink-400">
              Value over replacement: projected rest-of-season points above a replacement-level player at the same
              position.
            </p>
            <PlayerValueChart given={result.players_given} received={result.players_received} />
          </div>
        )}

        {tab === "positions" && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold">{pos.title}</h3>
            <p className="mb-3 mt-0.5 text-sm text-ink-400">{pos.note}</p>
            <PositionDeltaChart data={pos.data} unit={pos.unit} />
            <dl className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-ink-700 bg-ink-700 text-sm">
              <div className="bg-ink-800 px-3 py-2">
                <dt className="text-ink-400">Strengthens</dt>
                <dd className="mt-1 flex gap-1">{strengths.length ? strengths.map((p) => <PositionBadge key={p} position={p} />) : "—"}</dd>
              </div>
              <div className="bg-ink-800 px-3 py-2">
                <dt className="text-ink-400">Weakens</dt>
                <dd className="mt-1 flex gap-1">{weaknesses.length ? weaknesses.map((p) => <PositionBadge key={p} position={p} />) : "—"}</dd>
              </div>
            </dl>
          </div>
        )}

        {tab === "why" && (
          <div className="card p-4">
            <p className="text-[15px] leading-relaxed text-ink-100">{result.explanation.summary}</p>
            {result.explanation.details.length > 0 && (
              <ul className="mt-3 space-y-2 border-t border-ink-700 pt-3">
                {result.explanation.details.map((d) => (
                  <li key={d} className="flex gap-2.5 text-sm text-ink-300">
                    <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-500" />
                    {d}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
