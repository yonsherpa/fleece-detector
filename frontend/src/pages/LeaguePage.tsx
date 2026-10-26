import { Check, ChevronDown, Link2, Loader2, RefreshCw, Unlink } from "lucide-react";
import { useState, type FormEvent } from "react";
import { leagueSummary } from "../components/LeagueSwitcher";
import { ErrorState, PlayerAvatar, PositionBadge, cx } from "../components/ui";
import { useEspnLeague } from "../hooks/useEspnLeague";
import { POSITIONS, type ImportedTeam, type Position } from "../types/api";

/**
 * Pull ids out of a pasted ESPN URL ("...?leagueId=123456&teamId=1...") or a bare league number.
 * A team URL also tells us which team is yours.
 */
export function parseLeagueInput(input: string): { leagueId: number; teamId: number | null } | null {
  const fromUrl = input.match(/leagueId=(\d+)/i)?.[1];
  const digits = fromUrl ?? input.trim();
  if (!/^\d{1,12}$/.test(digits)) return null;
  const team = input.match(/teamId=(\d+)/i)?.[1];
  return { leagueId: Number(digits), teamId: team ? Number(team) : null };
}

function ConnectForm() {
  const { connect, loading, error } = useEspnLeague();
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = parseLeagueInput(input);
    if (parsed == null) {
      setInputError("Enter a league ID (digits only) or paste your ESPN league URL.");
      return;
    }
    await connect(parsed.leagueId, parsed.teamId);
  };

  return (
    <div className="mx-auto max-w-xl">
      <div className="card p-5">
        <h2 className="text-base font-semibold">Import your ESPN league</h2>
        <p className="mt-1 text-sm text-ink-400">
          Brings in your league's scoring, lineup and every team's roster, so grades and suggestions match your real
          league.
        </p>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <label htmlFor="league-id" className="sr-only">
            ESPN league ID or URL
          </label>
          <input
            id="league-id"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setInputError(null);
            }}
            inputMode="numeric"
            placeholder="League ID, e.g. 1234567"
            className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-mint-500/60"
          />
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
            {loading ? "Importing…" : "Import league"}
          </button>
        </form>
        {inputError && <p className="mt-2 text-sm text-flag-400">{inputError}</p>}
        {error && (
          <div className="mt-3">
            <ErrorState message={error} />
          </div>
        )}
        <ul className="mt-4 space-y-1.5 border-t border-ink-700 pt-4 text-xs text-ink-400">
          <li>
            Find the ID in your league's web address:{" "}
            <span className="num text-ink-300">fantasy.espn.com/football/league?leagueId=</span>
            <span className="num text-mint-400">1234567</span>. You can paste the whole URL.
          </li>
          <li>Public leagues only. Fleece Detector never asks for your ESPN password or login cookies.</li>
          <li>Private league? A league manager can make it viewable to the public in ESPN's league settings, or you can enter your roster by hand on the Trade page.</li>
        </ul>
      </div>
    </div>
  );
}

function TeamRow({ team, mine, onChoose }: { team: ImportedTeam; mine: boolean; onChoose: () => void }) {
  const [open, setOpen] = useState(false);
  const skill = team.players.filter((p) => (POSITIONS as string[]).includes(p.position));
  const top = skill.filter((p) => p.player_id).slice(0, 5);
  return (
    <li className={cx("border-b border-ink-700/60 last:border-b-0", mine && "bg-mint-500/[0.05]")}>
      <div className="flex items-center gap-3 px-4 py-2.5">
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={`Show ${team.name} roster`}
          className="rounded p-1 text-ink-400 hover:bg-ink-700 hover:text-ink-100"
        >
          <ChevronDown className={cx("h-4 w-4 transition-transform", open && "rotate-180")} />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-ink-100">{team.name}</span>
            <span className="text-xs text-ink-500">{team.abbrev}</span>
          </div>
          <div className="text-xs text-ink-400">{team.player_ids.length} players matched</div>
        </div>
        <div className="hidden -space-x-2 sm:flex" aria-hidden>
          {top.map((p) => (
            <span key={p.espn_id} className="rounded-full ring-2 ring-ink-800">
              <PlayerAvatar player={{ player_id: p.player_id!, name: p.name }} size={26} />
            </span>
          ))}
        </div>
        {mine ? (
          <span className="inline-flex items-center gap-1 rounded-md bg-mint-500/15 px-2 py-1 text-xs font-medium text-mint-400">
            <Check className="h-3 w-3" /> You
          </span>
        ) : (
          <button
            onClick={onChoose}
            className="rounded-md border border-ink-700 px-2 py-1 text-xs text-ink-300 hover:border-mint-500/50 hover:text-ink-100"
          >
            This is me
          </button>
        )}
      </div>
      {open && (
        <ul className="grid gap-x-6 border-t border-ink-700/60 bg-ink-850/50 px-4 py-2 sm:grid-cols-2">
          {team.players.map((p) => (
            <li key={p.espn_id} className="flex items-center gap-2 py-1 text-sm">
              {(POSITIONS as string[]).includes(p.position) ? (
                <PositionBadge position={p.position as Position} />
              ) : (
                <span className="inline-flex h-[18px] items-center rounded bg-ink-700 px-1.5 text-[10px] font-semibold text-ink-400">
                  {p.position}
                </span>
              )}
              <span className={cx("truncate", p.player_id ? "text-ink-100" : "text-ink-500")}>{p.name}</span>
              <span className="ml-auto shrink-0 text-xs text-ink-500">
                {p.lineup_slot === "IR" ? "IR" : p.player_id ? p.lineup_slot.toLowerCase() : p.position === "K" || p.position === "DST" ? "not modeled" : "no projection"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function Connected() {
  const { league, myTeam, loading, error, refresh, chooseMyTeam, applySettings, disconnect } = useEspnLeague();
  const [showUnmatched, setShowUnmatched] = useState(false);
  if (!league) return null;
  const lineup = league.league_settings.lineup;
  const lineupText = [
    `${lineup.QB} QB`,
    `${lineup.RB} RB`,
    `${lineup.WR} WR`,
    `${lineup.TE} TE`,
    lineup.FLEX && `${lineup.FLEX} FLEX`,
    lineup.SUPERFLEX && `${lineup.SUPERFLEX} SFLX`,
    `${lineup.BENCH} bench`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-4">
      <section className="card">
        <div className="flex flex-wrap items-start justify-between gap-3 p-4">
          <div>
            <h2 className="text-base font-semibold">{league.name}</h2>
            <p className="mt-0.5 text-sm text-ink-400">
              ESPN · {league.season} · {league.current_week ? `week ${league.current_week} · ` : ""}
              {leagueSummary(league.league_settings)}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={refresh}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-md border border-ink-700 px-2.5 py-1.5 text-xs text-ink-300 hover:text-ink-100"
            >
              <RefreshCw className={cx("h-3.5 w-3.5", loading && "animate-spin")} /> Refresh
            </button>
            <button
              onClick={disconnect}
              className="inline-flex items-center gap-1.5 rounded-md border border-ink-700 px-2.5 py-1.5 text-xs text-ink-300 hover:border-flag-400/50 hover:text-flag-400"
            >
              <Unlink className="h-3.5 w-3.5" /> Disconnect
            </button>
          </div>
        </div>
        <dl className="grid gap-px border-t border-ink-700 bg-ink-700 text-sm sm:grid-cols-3">
          <div className="bg-ink-800 px-4 py-3">
            <dt className="label">Scoring</dt>
            <dd className="mt-1 text-ink-100">{league.scoring_summary.join(" · ")}</dd>
          </div>
          <div className="bg-ink-800 px-4 py-3">
            <dt className="label">Lineup</dt>
            <dd className="mt-1 text-ink-100">{lineupText}</dd>
          </div>
          <div className="bg-ink-800 px-4 py-3">
            <dt className="label">Players</dt>
            <dd className="mt-1 text-ink-100">
              {league.matched_count} matched
              {league.unmatched.length > 0 && (
                <button onClick={() => setShowUnmatched((s) => !s)} className="ml-1 text-ink-400 underline underline-offset-2">
                  · {league.unmatched.length} without projections
                </button>
              )}
              {league.unsupported_count > 0 && <span className="text-ink-400"> · {league.unsupported_count} K/DST</span>}
            </dd>
          </div>
        </dl>
        {showUnmatched && (
          <p className="border-t border-ink-700 px-4 py-2 text-xs text-ink-400">{league.unmatched.join(", ")}</p>
        )}
        {league.notes.length > 0 && (
          <ul className="space-y-1 border-t border-ink-700 px-4 py-3 text-xs text-ink-400">
            {league.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 px-4 py-2.5 text-xs text-ink-500">
          <span>Your scoring, league size and lineup were set from this league.</span>
          <button onClick={applySettings} className="text-ink-300 hover:text-ink-100">
            Re-apply league settings
          </button>
        </div>
      </section>

      {error && <ErrorState message={error} onRetry={refresh} />}

      <section className="card">
        <header className="border-b border-ink-700 px-4 py-3">
          <h2 className="text-sm font-semibold">{myTeam ? "Teams" : "Which team is yours?"}</h2>
          <p className="mt-0.5 text-xs text-ink-400">
            {myTeam
              ? `Your roster on the Trade and Moves pages stays synced with ${myTeam.name}.`
              : "Pick your team to load your roster everywhere. Other teams become trade partners."}
          </p>
        </header>
        <ul>
          {league.teams.map((t) => (
            <TeamRow key={t.team_id} team={t} mine={t.team_id === myTeam?.team_id} onChoose={() => chooseMyTeam(t.team_id)} />
          ))}
        </ul>
      </section>
    </div>
  );
}

export function LeaguePage() {
  const { league, loading } = useEspnLeague();
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold">League</h1>
        <p className="mt-1 text-sm text-ink-400">Connect a public ESPN league to fill in settings and rosters automatically.</p>
      </div>
      {league ? <Connected /> : loading ? <p className="text-sm text-ink-400">Loading your league…</p> : <ConnectForm />}
    </div>
  );
}
