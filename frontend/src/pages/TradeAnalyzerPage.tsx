import { ArrowDownUp, Loader2, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { RosterSection } from "../components/trade/Rosters";
import { TradeSide } from "../components/trade/TradePanel";
import { ResultDetails, Verdict } from "../components/trade/TradeResults";
import { ErrorState, Skeleton, cx } from "../components/ui";
import { useEspnLeague } from "../hooks/useEspnLeague";
import { useLeague } from "../hooks/useLeagueSettings";
import { MY_ROSTER_KEY, useRoster } from "../hooks/useRoster";
import { ApiError, api, leagueKey } from "../services/api";
import { maxRosterSize, type PlayerValue, type TradeEvaluation } from "../types/api";
import type { TradePrefill } from "./MovesPage";

export function TradeAnalyzerPage() {
  const { league } = useLeague();
  const [gives, setGives] = useState<PlayerValue[]>([]);
  const [receives, setReceives] = useState<PlayerValue[]>([]);
  const [result, setResult] = useState<TradeEvaluation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLElement>(null);

  const selectedIds = useMemo(
    () => new Set([...gives, ...receives].map((p) => p.player_id)),
    [gives, receives],
  );

  const rosterA = useRoster(league, MY_ROSTER_KEY);
  const rosterB = useRoster(league);
  const espn = useEspnLeague();

  // Arriving from a Moves suggestion ("Shop" / "Trade for"): start the offer with that player,
  // and load the owning league team as "their roster" so both sides get graded.
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const prefill = location.state as TradePrefill | null;
    if (!prefill?.give && !prefill?.receive) return;
    navigate(location.pathname, { replace: true, state: null }); // don't re-apply on refresh or Back
    const partner = espn.league?.teams.find((t) => t.name === prefill.partnerTeam);
    if (partner) rosterB.replace(partner.player_ids);
    const addTo = (setter: typeof setGives, id?: string) =>
      id &&
      api
        .getPlayer(id, league)
        .then((p) => setter((list) => (list.some((x) => x.player_id === p.player_id) ? list : [...list, p])))
        .catch(() => setError("Couldn't load that player for the trade."));
    addTo(setGives, prefill.give);
    addTo(setReceives, prefill.receive);
    // Runs once per navigation; location.state is what changes.
  }, [location.state]);
  const maxSize = maxRosterSize(league.lineup);
  const hasA = rosterA.ids.length > 0;
  const hasB = rosterB.ids.length > 0;
  const oversized = rosterA.ids.length > maxSize || rosterB.ids.length > maxSize;

  // Keep the trade consistent with the rosters (the backend enforces the same rules):
  // Team A can only give players on its roster, and can't receive players it already has.
  const rosterKey = `${rosterA.ids.join()}|${rosterB.ids.join()}`;
  useEffect(() => {
    const a = new Set(rosterA.ids);
    const b = new Set(rosterB.ids);
    const keep = <T,>(list: T[], next: T[]) => (next.length === list.length ? list : next);
    setGives((g) => keep(g, hasA ? g.filter((p) => a.has(p.player_id)) : g));
    setReceives((r) => keep(r, r.filter((p) => !a.has(p.player_id) && (!hasB || b.has(p.player_id)))));
    setResult(null);
    // rosterKey captures every roster change; the sets are rebuilt from it.
  }, [rosterKey]);

  // Player values depend on league settings, so refresh selected players and drop stale results.
  useEffect(() => {
    setResult(null);
    const refresh = (list: PlayerValue[]) => Promise.all(list.map((p) => api.getPlayer(p.player_id, league)));
    if (gives.length + receives.length === 0) return;
    Promise.all([refresh(gives), refresh(receives)])
      .then(([g, r]) => {
        setGives(g);
        setReceives(r);
      })
      .catch(() => setError("Couldn't refresh player values for the new league settings."));
    // Only league changes should trigger this; including gives/receives would loop on our own updates.
  }, [leagueKey(league)]);

  const edit = (fn: () => void) => {
    fn();
    setResult(null);
    setError(null);
  };

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.evaluateTrade({
        team_a_gives: gives.map((p) => p.player_id),
        team_a_receives: receives.map((p) => p.player_id),
        // Send only players the dataset still knows; stale saved ids are flagged in the roster editor.
        team_a_roster: hasA ? rosterA.players.map((p) => p.player_id) : null,
        team_b_roster: hasB ? rosterB.players.map((p) => p.player_id) : null,
        league,
      });
      setResult(res);
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Trade evaluation failed unexpectedly.");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => edit(() => {
    setGives([]);
    setReceives([]);
  });

  const canAnalyze = gives.length > 0 && receives.length > 0 && !loading && !oversized;
  const hint = oversized
    ? `A roster has more than ${maxSize} players. Fix it in Rosters or Lineup settings.`
    : gives.length === 0 || receives.length === 0
      ? hasA
        ? "Pick who you're giving from your roster, and who you're getting."
        : "Add at least one player to each side."
      : !hasA
        ? "Tip: add your roster to see how your starting lineup changes."
        : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Are you getting fleeced?</h1>
          <p className="mt-1 text-sm text-ink-400">
            Build the offer, then evaluate it against your league's scoring, size and lineup.
          </p>
        </div>
        {/* Always rendered (just hidden) so adding the first player doesn't shift the layout. */}
        <button
          onClick={reset}
          disabled={selectedIds.size === 0}
          className={cx(
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-ink-400 hover:bg-ink-800 hover:text-ink-100",
            selectedIds.size === 0 && "invisible max-sm:hidden",
          )}
        >
          <RotateCcw className="h-3.5 w-3.5" /> Clear trade
        </button>
      </div>

      <RosterSection rosterA={rosterA} rosterB={rosterB} max={maxSize} />

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        {/* The trade offer */}
        <div className="card">
          <TradeSide
            label="You send"
            badge="You"
            tone="give"
            players={gives}
            pool={hasA ? rosterA.players : undefined}
            excludeIds={selectedIds}
            onAdd={(p) => edit(() => setGives((g) => [...g, p]))}
            onRemove={(id) => edit(() => setGives((g) => g.filter((p) => p.player_id !== id)))}
          />
          <div className="relative border-t border-ink-700" aria-hidden>
            <span className="absolute left-1/2 top-0 grid h-6 w-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-ink-700 bg-ink-800 text-ink-400">
              <ArrowDownUp className="h-3 w-3" />
            </span>
          </div>
          <TradeSide
            label="You receive"
            badge="B"
            tone="receive"
            players={receives}
            pool={hasB ? rosterB.players : undefined}
            excludeIds={new Set([...selectedIds, ...rosterA.ids])}
            onAdd={(p) => edit(() => setReceives((r) => [...r, p]))}
            onRemove={(id) => edit(() => setReceives((r) => r.filter((p) => p.player_id !== id)))}
          />
          <div className="flex flex-col gap-2 border-t border-ink-700 p-4 sm:flex-row sm:items-center">
            <button onClick={analyze} disabled={!canAnalyze} className="btn-primary sm:w-auto">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Evaluating…" : "Evaluate trade"}
            </button>
            {hint && !loading && (
              <p className={cx("text-xs", oversized ? "text-flag-400" : "text-ink-500")}>{hint}</p>
            )}
          </div>
        </div>

        {/* The verdict */}
        <aside ref={resultsRef} className="card scroll-mt-28 lg:sticky lg:top-28">
          {error ? (
            <div className="p-4">
              <ErrorState message={error} onRetry={canAnalyze ? analyze : undefined} />
            </div>
          ) : loading ? (
            <VerdictSkeleton />
          ) : result ? (
            <Verdict result={result} />
          ) : (
            <HowItWorks />
          )}
        </aside>
      </div>

      {result && !loading && (
        <div className="mt-6">
          <ResultDetails result={result} />
        </div>
      )}
    </div>
  );
}

const STEPS = [
  ["Value every player", "Projected rest-of-season points above a replacement-level player at the same position."],
  ["Compare both sides", "Fairness checks whether the value exchanged is balanced. Filler players don't add value."],
  ["Grade the deal", "A+ to F for each team. With your roster, it grades the change in your best starting lineup."],
];

/** Shown in the verdict panel before the first evaluation. */
function HowItWorks() {
  return (
    <div className="p-4">
      <div className="text-sm font-semibold text-ink-100">Verdict</div>
      <p className="mt-1 text-sm text-ink-400">Add players to both sides and evaluate the trade.</p>
      <ol className="mt-4 space-y-3 border-t border-ink-700 pt-4">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="num grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ink-700 text-[10px] text-ink-300">
              {i + 1}
            </span>
            <div>
              <div className="text-sm text-ink-100">{title}</div>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-400">{body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function VerdictSkeleton() {
  return (
    <div className="space-y-3 p-4" aria-busy="true" aria-label="Evaluating trade">
      <div className="flex items-center gap-4">
        <Skeleton className="h-12 w-14" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-5" />
      ))}
    </div>
  );
}
