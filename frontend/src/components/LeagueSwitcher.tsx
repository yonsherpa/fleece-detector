import { ChevronDown, Minus, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useEspnLeague } from "../hooks/useEspnLeague";
import { useLeague } from "../hooks/useLeagueSettings";
import {
  DEFAULT_LINEUP,
  SLOT_LIMITS,
  SLOT_NAMES,
  maxRosterSize,
  type LeagueSettings,
  type ScoringFormat,
  type SlotName,
} from "../types/api";
import { cx } from "./ui";

const FORMATS: { value: ScoringFormat; label: string }[] = [
  { value: "ppr", label: "PPR" },
  { value: "half_ppr", label: "Half PPR" },
  { value: "standard", label: "Standard" },
];
const TEAM_COUNTS = [8, 10, 12, 14, 16];
const SLOT_HELP: Partial<Record<SlotName, string>> = { FLEX: "RB/WR/TE", SUPERFLEX: "Any position" };

export function leagueSummary(league: LeagueSettings): string {
  const format = FORMATS.find((f) => f.value === league.scoring_format)?.label ?? "custom scoring";
  return `${league.num_teams}-team ${format}${league.lineup.SUPERFLEX > 0 ? " · Superflex" : ""}`;
}

/**
 * One place for every league setting (scoring, size, lineup slots). They all change
 * player values, so they live in the top bar like a project switcher.
 */
export function LeagueSwitcher() {
  const { league, setLeague } = useLeague();
  const espn = useEspnLeague();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const lineup = league.lineup;
  // An imported league's own scoring is offered alongside the presets.
  const formats = league.scoring ? [...FORMATS, { value: "custom" as const, label: "League" }] : FORMATS;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const changeSlot = (slot: SlotName, delta: number) => {
    const next = { ...lineup, [slot]: Math.min(SLOT_LIMITS[slot], Math.max(0, lineup[slot] + delta)) };
    if (maxRosterSize(next) - next.BENCH === 0) return; // keep at least one starter
    setLeague({ lineup: next });
  };

  return (
    <div ref={ref} className="relative min-w-0">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label="League settings"
        className={cx(
          "flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors",
          open ? "bg-ink-800" : "hover:bg-ink-800",
        )}
      >
        <span className="hidden max-w-[12rem] truncate font-medium text-ink-100 sm:inline">{espn.league?.name ?? "My league"}</span>
        <span className="truncate text-ink-400">{leagueSummary(league)}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-ink-400" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-40 mt-1.5 w-[19rem] max-w-[calc(100vw-2rem)] rounded-lg border border-ink-700 bg-ink-850 shadow-xl shadow-black/40">
          <div className="space-y-4 p-4">
            <div>
              <div className="label mb-1.5">Scoring</div>
              <div role="radiogroup" aria-label="Scoring format" className={cx("grid gap-1 rounded-md bg-ink-900 p-0.5", formats.length === 4 ? "grid-cols-4" : "grid-cols-3")}>
                {formats.map((f) => (
                  <button
                    key={f.value}
                    role="radio"
                    aria-checked={league.scoring_format === f.value}
                    onClick={() => setLeague({ scoring_format: f.value })}
                    className={cx(
                      "rounded px-2 py-1 text-xs font-medium transition-colors",
                      league.scoring_format === f.value ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-100",
                    )}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="label mb-1.5">Teams</div>
              <div className="grid grid-cols-5 gap-1 rounded-md bg-ink-900 p-0.5">
                {TEAM_COUNTS.map((n) => (
                  <button
                    key={n}
                    onClick={() => setLeague({ num_teams: n })}
                    aria-pressed={league.num_teams === n}
                    className={cx(
                      "num rounded px-2 py-1 text-xs transition-colors",
                      league.num_teams === n ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-100",
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="label">Lineup slots</span>
                <button onClick={() => setLeague({ lineup: DEFAULT_LINEUP })} className="text-xs text-ink-400 hover:text-ink-100">
                  ESPN default
                </button>
              </div>
              <ul className="divide-y divide-ink-700/60 rounded-md border border-ink-700">
                {SLOT_NAMES.map((slot) => (
                  <li key={slot} className="flex items-center justify-between px-3 py-1.5">
                    <span className="text-sm text-ink-200">
                      {slot === "SUPERFLEX" ? "Superflex" : slot === "BENCH" ? "Bench" : slot}
                      {SLOT_HELP[slot] && <span className="ml-1.5 text-xs text-ink-500">{SLOT_HELP[slot]}</span>}
                    </span>
                    <span className="flex items-center gap-1">
                      <Stepper label={`Remove a ${slot} slot`} onClick={() => changeSlot(slot, -1)} disabled={lineup[slot] === 0}>
                        <Minus className="h-3 w-3" />
                      </Stepper>
                      <span className="num w-5 text-center text-sm text-ink-100">{lineup[slot]}</span>
                      <Stepper
                        label={`Add a ${slot} slot`}
                        onClick={() => changeSlot(slot, 1)}
                        disabled={lineup[slot] >= SLOT_LIMITS[slot]}
                      >
                        <Plus className="h-3 w-3" />
                      </Stepper>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-ink-500">
                {maxRosterSize(lineup)}-player rosters. Kickers and defenses aren't modeled, so leave them out.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stepper({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="grid h-6 w-6 place-items-center rounded text-ink-400 transition-colors hover:bg-ink-700 hover:text-ink-100 disabled:opacity-30"
    >
      {children}
    </button>
  );
}
