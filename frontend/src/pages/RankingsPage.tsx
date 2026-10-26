import { ArrowDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { leagueSummary } from "../components/LeagueSwitcher";
import { ErrorState, PlayerIdentity, Skeleton, cx, fmt } from "../components/ui";
import { useDebounce } from "../hooks/useDebounce";
import { useLeague } from "../hooks/useLeagueSettings";
import { usePlayers } from "../hooks/usePlayers";
import { POSITIONS, type PlayerValue, type Position } from "../types/api";

type SortKey = "value_over_replacement" | "projected_ros_points" | "projected_ppg" | "games_remaining";

const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "games_remaining", label: "Games", className: "hidden md:table-cell" },
  { key: "projected_ppg", label: "PPG", className: "hidden sm:table-cell" },
  { key: "projected_ros_points", label: "ROS pts" },
  { key: "value_over_replacement", label: "Value" },
];

export function RankingsPage() {
  const { league } = useLeague();
  const [position, setPosition] = useState<Position | undefined>();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("value_over_replacement");
  const q = useDebounce(query.trim(), 200);
  const { players, total, loading, error, reload } = usePlayers(league, { q, position, limit: 500 });

  const sorted = useMemo(
    () => [...players].sort((a, b) => (b[sortKey] ?? -1) - (a[sortKey] ?? -1)),
    [players, sortKey],
  );
  const maxValue = Math.max(1, ...players.map((p) => p.value_over_replacement));

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold">Rankings</h1>
        <p className="mt-1 text-sm text-ink-400">
          Rest-of-season value: projected points above a replacement-level player at the same position, for{" "}
          {leagueSummary(league)} leagues.
        </p>
      </div>

      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-0.5 rounded-md border border-ink-700 bg-ink-850 p-0.5">
          {[undefined, ...POSITIONS].map((p) => (
            <button
              key={p ?? "ALL"}
              onClick={() => setPosition(p)}
              aria-pressed={position === p}
              className={cx(
                "rounded px-3 py-1 text-xs font-medium transition-colors",
                position === p ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-100",
              )}
            >
              {p ?? "All"}
            </button>
          ))}
        </div>
        <div className="relative sm:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name or team"
            aria-label="Filter players"
            className="w-full rounded-md border border-ink-700 bg-ink-900 py-1.5 pl-9 pr-3 text-sm text-ink-100 placeholder:text-ink-500 focus:border-mint-500/60"
          />
        </div>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-700 bg-ink-850 text-left">
                  <th className="label w-12 px-4 py-2 font-medium">#</th>
                  <th className="label px-2 py-2 font-medium">Player</th>
                  {COLUMNS.map((c) => (
                    <th key={c.key} className={cx("px-3 py-2 text-right", c.className)}>
                      <button
                        onClick={() => setSortKey(c.key)}
                        className={cx("label inline-flex items-center gap-1", sortKey === c.key && "text-ink-100")}
                        aria-sort={sortKey === c.key ? "descending" : undefined}
                      >
                        {c.label}
                        {sortKey === c.key && <ArrowDown className="h-3 w-3" />}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="border-b border-ink-700/50">
                        <td colSpan={6} className="px-4 py-3">
                          <Skeleton className="h-5" />
                        </td>
                      </tr>
                    ))
                  : sorted.map((p, i) => <Row key={p.player_id} p={p} rank={i + 1} maxValue={maxValue} />)}
                {!loading && sorted.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-ink-400">
                      No players match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {!loading && (
            <div className="border-t border-ink-700 px-4 py-2 text-xs text-ink-500">
              Showing {sorted.length} of {total} players
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ p, rank, maxValue }: { p: PlayerValue; rank: number; maxValue: number }) {
  return (
    <tr className="border-b border-ink-700/50 transition-colors hover:bg-ink-850">
      <td className="num px-4 py-2 text-ink-500">{rank}</td>
      <td className="px-2 py-2">
        <PlayerIdentity p={p} size={32} />
      </td>
      <td className="num hidden px-3 py-2 text-right text-ink-400 md:table-cell">{p.games_remaining}</td>
      <td className="num hidden px-3 py-2 text-right text-ink-300 sm:table-cell">{fmt(p.projected_ppg)}</td>
      <td className="num px-3 py-2 text-right text-ink-300">
        {p.projection_available ? p.projected_ros_points.toFixed(0) : <span className="text-ink-500">n/a</span>}
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center justify-end gap-2">
          <div className="hidden h-1 w-14 overflow-hidden rounded-full bg-ink-700 sm:block">
            <div
              className="h-full rounded-full bg-mint-500"
              style={{ width: `${(p.value_over_replacement / maxValue) * 100}%` }}
            />
          </div>
          <span className="num w-12 font-medium text-ink-100">{p.value_over_replacement.toFixed(1)}</span>
        </div>
      </td>
    </tr>
  );
}
