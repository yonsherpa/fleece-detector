import { AlertTriangle, RefreshCw } from "lucide-react";
import { useState } from "react";
import type { PlayerValue, Position } from "../types/api";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function fmt(n: number | null | undefined, digits = 1): string {
  return n == null ? "—" : n.toFixed(digits);
}

export function signed(n: number, digits = 1): string {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}`;
}

const POSITION_STYLES: Record<Position, string> = {
  QB: "bg-pos-qb/15 text-pos-qb",
  RB: "bg-pos-rb/15 text-pos-rb",
  WR: "bg-pos-wr/15 text-pos-wr",
  TE: "bg-pos-te/15 text-pos-te",
};

/** Sleeper-style position pill, e.g. "RB" or "RB10" (position rank). */
export function PositionBadge({ position, rank }: { position: Position; rank?: number | null }) {
  return (
    <span
      className={cx(
        "inline-flex h-[18px] items-center rounded px-1.5 text-[10px] font-semibold tracking-wide",
        POSITION_STYLES[position],
      )}
    >
      {position}
      {rank != null && rank}
    </span>
  );
}

/** Headshot from Sleeper's CDN (our ids are Sleeper ids). Falls back to initials if there's no photo. */
export function PlayerAvatar({ player, size = 36 }: { player: Pick<PlayerValue, "player_id" | "name">; size?: number }) {
  const [failed, setFailed] = useState(false);
  const sleeperId = player.player_id.startsWith("sleeper-") ? player.player_id.slice("sleeper-".length) : null;
  const initials = player.name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
  return (
    <span
      className="relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full bg-ink-700 text-[10px] font-semibold text-ink-300"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {sleeperId && !failed ? (
        <img
          src={`https://sleepercdn.com/content/nfl/players/thumb/${sleeperId}.jpg`}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        initials
      )}
    </span>
  );
}

export function InjuryTag({ status }: { status: string | null }) {
  if (!status || status.toUpperCase() === "ACTIVE") return null;
  const upper = status.toUpperCase();
  const severe = ["OUT", "IR", "DOUBTFUL", "PUP", "SUS"].includes(upper);
  return (
    <span
      title={`Injury status reported by the data source: ${status}`}
      className={cx("text-[10px] font-semibold", severe ? "text-flag-400" : "text-amber-400")}
    >
      {upper === "QUESTIONABLE" ? "Q" : upper}
    </span>
  );
}

/** Avatar + name + position pill + team line: the standard way a player appears everywhere. */
export function PlayerIdentity({
  p,
  size = 36,
  detail,
}: {
  p: PlayerValue;
  size?: number;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <PlayerAvatar player={p} size={size} />
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium text-ink-100">{p.name}</span>
          <InjuryTag status={p.injury_status} />
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs text-ink-400">
          <PositionBadge position={p.position} rank={p.positional_rank} />
          <span className="truncate">{detail ?? `${p.nfl_team}${p.bye_week != null ? ` · bye ${p.bye_week}` : ""}`}</span>
        </div>
      </div>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cx("relative overflow-hidden rounded-md bg-ink-800", className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/[0.03] to-transparent" />
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-flag-400/30 bg-flag-500/[0.08] p-3 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-flag-400" />
      <div className="flex-1 text-ink-200">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-ink-100 hover:bg-ink-700"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </button>
      )}
    </div>
  );
}
