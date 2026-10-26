import { ArrowLeftRight } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { RosterSection } from "../components/trade/Rosters";
import { ErrorState, PlayerIdentity, Skeleton, cx, signed } from "../components/ui";
import { useEspnLeague } from "../hooks/useEspnLeague";
import { useLeague } from "../hooks/useLeagueSettings";
import { MY_ROSTER_KEY, useRoster } from "../hooks/useRoster";
import { ApiError, api, leagueKey } from "../services/api";
import { maxRosterSize, type MoveSuggestion, type MovesResponse } from "../types/api";

/** What the trade page should pre-fill when you jump there from a suggestion. */
export interface TradePrefill {
  give?: string;
  receive?: string;
  /** League team that owns `receive`; the trade page loads them as "their roster". */
  partnerTeam?: string;
}

function compact(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}K` : String(n);
}

function Metric({ value, label, tone }: { value: string; label: string; tone?: "up" | "down" | "muted" }) {
  return (
    <div className="w-12 shrink-0 text-right sm:w-16">
      <div
        className={cx(
          "num text-sm",
          tone === "up" ? "text-mint-400" : tone === "down" ? "text-flag-400" : tone === "muted" ? "text-ink-400" : "text-ink-100",
        )}
      >
        {value}
      </div>
      <div className="text-[10px] text-ink-500">{label}</div>
    </div>
  );
}

function gainMetric(s: MoveSuggestion) {
  if (s.lineup_change == null) return null;
  return (
    <Metric
      value={s.lineup_change > 0 ? signed(s.lineup_change) : "+0"}
      label="lineup"
      tone={s.lineup_change > 0 ? "up" : "muted"}
    />
  );
}

interface SectionProps {
  title: string;
  rule: string;
  children: ReactNode;
  empty?: string | null;
  className?: string;
  right?: ReactNode;
  listClassName?: string;
}

function Section({ title, rule, children, empty, className, right, listClassName }: SectionProps) {
  return (
    <section className={cx("card flex min-w-0 flex-col", className)}>
      <header className="flex items-start justify-between gap-3 border-b border-ink-700 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-0.5 text-xs text-ink-400">{rule}</p>
        </div>
        {right}
      </header>
      {empty ? <p className="px-4 py-5 text-sm text-ink-400">{empty}</p> : <ul className={listClassName}>{children}</ul>}
    </section>
  );
}

function Row({ s, children, action }: { s: MoveSuggestion; children?: ReactNode; action?: ReactNode }) {
  // With an imported league, show who owns the player instead of the bye week.
  const detail = s.owner_team ? `${s.player.nfl_team} · ${s.owner_team}` : undefined;
  return (
    <li className="flex items-center gap-3 border-b border-ink-700/50 px-4 py-2.5 last:border-b-0" title={s.reason}>
      <PlayerIdentity p={s.player} size={32} detail={detail} />
      {children}
      {action}
    </li>
  );
}

function TradeButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className="inline-flex shrink-0 items-center gap-1 rounded-md border border-ink-700 px-2 py-1 text-xs text-ink-300 transition-colors hover:border-mint-500/50 hover:text-ink-100"
    >
      <ArrowLeftRight className="h-3 w-3" />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function MovesSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2" aria-busy="true" aria-label="Loading suggestions">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card space-y-3 p-4">
          <Skeleton className="h-4 w-1/3" />
          {Array.from({ length: 4 }).map((_, j) => (
            <Skeleton key={j} className="h-8" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function MovesPage() {
  const { league } = useLeague();
  const espn = useEspnLeague();
  const roster = useRoster(league, MY_ROSTER_KEY);
  const navigate = useNavigate();
  const [data, setData] = useState<MovesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [trendKind, setTrendKind] = useState<"adds" | "drops">("adds");
  const [reloadKey, setReloadKey] = useState(0);

  // Only ids the dataset still knows are sent; stale ones are flagged in the roster editor.
  const knownIds = roster.players.map((p) => p.player_id);
  // Every team's roster from an imported league makes waiver targets real free agents.
  const leagueRosters = espn.league?.teams.map((t) => ({ team_name: t.name, player_ids: t.player_ids })) ?? null;
  const requestKey = `${leagueKey(league)}#${knownIds.join(",")}#${espn.league?.fetched_at ?? ""}#${reloadKey}`;

  useEffect(() => {
    if (roster.ids.length > 0 && knownIds.length === 0 && !roster.error) return; // roster values still loading
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .moves(knownIds.length ? knownIds : null, league, leagueRosters)
      .then((res) => !cancelled && setData(res))
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load suggestions.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // requestKey captures league, roster and retries.
  }, [requestKey]);

  const openTrade = (prefill: TradePrefill) => navigate("/", { state: prefill });
  const noRoster = data && !data.has_roster ? "Add your roster above to see this." : null;
  const trending = trendKind === "adds" ? data?.trending_adds : data?.trending_drops;

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold">Moves</h1>
        <p className="mt-1 text-sm text-ink-400">
          Who to sell, drop, pick up or trade for, measured by what each move does to your best starting lineup.
        </p>
      </div>

      <RosterSection rosterA={roster} max={maxRosterSize(league.lineup)} hint="add it for personal suggestions" />

      {error && <ErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />}
      {loading && !data && <MovesSkeleton />}

      {data && (
        <div className={cx("space-y-4 transition-opacity", loading && "opacity-60")}>
          {data.notes.length > 0 && (
            <ul className="space-y-1 text-sm text-ink-400">
              {data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}

          <div className="grid items-start gap-4 md:grid-cols-2">
            <Section
              title="Sell high"
              rule="Worth a lot to other teams, but barely used in your lineup."
              empty={noRoster ?? (data.sell_high.length ? null : "No surplus: your valuable players all start.")}
            >
              {data.sell_high.map((s) => (
                <Row key={s.player.player_id} s={s} action={<TradeButton label="Shop" onClick={() => openTrade({ give: s.player.player_id })} />}>
                  <Metric value={s.player.value_over_replacement.toFixed(1)} label="value" />
                  <Metric value={s.lineup_change ? signed(s.lineup_change) : "0"} label="lineup" tone="muted" />
                </Row>
              ))}
            </Section>

            <Section
              title="Buy targets"
              rule={
                (data.buy_budget != null
                  ? `Biggest upgrades worth no more than about your best sell-high piece (${data.buy_budget.toFixed(1)})`
                  : "Players who'd most improve your starting lineup") +
                (data.availability === "league" ? ", on other teams in your league." : ".")
              }
              empty={noRoster ?? (data.buy_targets.length ? null : "No affordable player would upgrade your lineup.")}
            >
              {data.buy_targets.map((s) => (
                <Row
                  key={s.player.player_id}
                  s={s}
                  action={
                    <TradeButton
                      label="Trade for"
                      onClick={() => openTrade({ receive: s.player.player_id, partnerTeam: s.owner_team ?? undefined })}
                    />
                  }
                >
                  {gainMetric(s)}
                  <Metric value={s.player.value_over_replacement.toFixed(1)} label="value" />
                </Row>
              ))}
            </Section>

            <Section
              title="Safe to drop"
              rule="At or below replacement level and never in your best lineup."
              empty={noRoster ?? (data.safe_to_drop.length ? null : "Nobody on your roster is dead weight.")}
            >
              {data.safe_to_drop.map((s) => (
                <Row key={s.player.player_id} s={s}>
                  <Metric value={s.player.projected_ros_points.toFixed(0)} label="ROS pts" tone="muted" />
                </Row>
              ))}
            </Section>

            <Section
              title="Waiver targets"
              rule={
                data.availability === "league"
                  ? `Free agents in ${espn.league?.name ?? "your league"}: on nobody's roster right now.`
                  : `Best projected players ranked outside the top ${data.rostered_cutoff}, so likely unrostered in your league. Import your league for real availability.`
              }
              empty={data.waiver_targets.length ? null : "No projected free agents found."}
            >
              {data.waiver_targets.map((s) => (
                <Row key={s.player.player_id} s={s}>
                  {gainMetric(s)}
                  <Metric value={s.player.projected_ros_points.toFixed(0)} label="ROS pts" tone={data.has_roster ? "muted" : undefined} />
                </Row>
              ))}
            </Section>
          </div>

          <Section
            title="Trending on Sleeper"
            rule={`Most ${trendKind === "adds" ? "added" : "dropped"} players across Sleeper leagues in the last ${data.trending.lookback_hours} hours. Popular isn't the same as useful to you.`}
            empty={
              !data.trending.available
                ? data.trending.message
                : trending && trending.length === 0
                  ? "No trending players right now."
                  : null
            }
            right={
              <div className="flex shrink-0 rounded-md border border-ink-700 bg-ink-850 p-0.5" role="tablist">
                {(["adds", "drops"] as const).map((k) => (
                  <button
                    key={k}
                    role="tab"
                    aria-selected={trendKind === k}
                    onClick={() => setTrendKind(k)}
                    className={cx(
                      "rounded px-2.5 py-1 text-xs font-medium",
                      trendKind === k ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-100",
                    )}
                  >
                    {k === "adds" ? "Adds" : "Drops"}
                  </button>
                ))}
              </div>
            }
            listClassName="grid md:grid-cols-2"
          >
            {trending?.map((s) => (
              <Row key={s.player.player_id} s={s}>
                {s.on_your_roster && <span className="shrink-0 text-[10px] text-amber-400">on your roster</span>}
                <Metric value={compact(s.trend_count ?? 0)} label={trendKind === "adds" ? "adds" : "drops"} />
                {trendKind === "adds" ? gainMetric(s) : <Metric value={s.player.projected_ros_points.toFixed(0)} label="ROS pts" tone="muted" />}
              </Row>
            ))}
          </Section>
          {data.trending.available && data.trending.unprojected_count > 0 && (
            <p className="text-xs text-ink-500">
              {data.trending.unprojected_count} trending player(s) aren't shown because they have no projected role yet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
