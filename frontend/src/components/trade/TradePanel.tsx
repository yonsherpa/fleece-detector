import { X } from "lucide-react";
import type { PlayerValue } from "../../types/api";
import { PlayerIdentity, cx, fmt } from "../ui";
import { PlayerSearch } from "./PlayerSearch";

export const MAX_PER_SIDE = 8;

interface Props {
  label: string;
  badge: string;
  tone: "give" | "receive";
  players: PlayerValue[];
  excludeIds: Set<string>;
  /** When set, players can only be picked from this list (a roster). */
  pool?: PlayerValue[];
  onAdd: (p: PlayerValue) => void;
  onRemove: (id: string) => void;
}

/** One side of the trade offer: header, player rows, and an "add player" search. */
export function TradeSide({ label, badge, tone, players, excludeIds, pool, onAdd, onRemove }: Props) {
  const totalRos = players.reduce((sum, p) => sum + p.projected_ros_points, 0);
  const totalValue = players.reduce((sum, p) => sum + p.value_over_replacement, 0);

  return (
    <section>
      <header className="flex items-center gap-2.5 px-4 pb-2 pt-3">
        <span
          className={cx(
            "grid h-6 w-6 place-items-center rounded-full text-[10px] font-semibold",
            tone === "give" ? "bg-flag-500/15 text-flag-400" : "bg-mint-500/15 text-mint-400",
          )}
          aria-hidden
        >
          {badge}
        </span>
        <h2 className="text-sm font-semibold">{label}</h2>
        {players.length > 0 && (
          <span className="ml-auto text-xs text-ink-400">
            <span className="num text-ink-200">{totalRos.toFixed(0)}</span> ROS pts ·{" "}
            <span className="num text-ink-200">{totalValue.toFixed(1)}</span> value
          </span>
        )}
      </header>

      <ul>
        {players.map((p) => (
          <li key={p.player_id} className="group flex items-center gap-3 border-t border-ink-700/60 px-4 py-2.5">
            <PlayerIdentity p={p} detail={`${p.nfl_team}${p.bye_week != null ? ` · bye ${p.bye_week}` : ""} · ${p.games_remaining} games left`} />
            {p.projection_available ? (
              <dl className="flex shrink-0 items-center gap-4 text-right">
                <Stat label="Proj ppg" value={fmt(p.projected_ppg)} className="hidden sm:block" />
                <Stat label="ROS pts" value={fmt(p.projected_ros_points, 0)} className="hidden sm:block" />
                <Stat label="Value" value={fmt(p.value_over_replacement)} strong />
              </dl>
            ) : (
              <span className="shrink-0 text-xs text-ink-500">No projection</span>
            )}
            <button
              onClick={() => onRemove(p.player_id)}
              aria-label={`Remove ${p.name}`}
              className="shrink-0 rounded p-1 text-ink-500 transition-colors hover:bg-ink-700 hover:text-ink-100"
            >
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>

      <div className="px-4 pb-3 pt-1">
        <PlayerSearch
          excludeIds={excludeIds}
          onSelect={onAdd}
          disabled={players.length >= MAX_PER_SIDE}
          pool={pool}
          placeholder={pool ? "Add from roster…" : "Add a player…"}
        />
      </div>
    </section>
  );
}

function Stat({ label, value, strong, className }: { label: string; value: string; strong?: boolean; className?: string }) {
  return (
    <div className={className}>
      <dd className={cx("num text-sm", strong ? "font-medium text-ink-100" : "text-ink-300")}>{value}</dd>
      <dt className="text-[10px] text-ink-500">{label}</dt>
    </div>
  );
}
