import { ChevronDown, Trash2, Users, X } from "lucide-react";
import { useState } from "react";
import { useEspnLeague } from "../../hooks/useEspnLeague";
import type { Roster } from "../../hooks/useRoster";
import { POSITIONS, type ImportedTeam, type PlayerValue } from "../../types/api";
import { InjuryTag, PlayerAvatar, PositionBadge, cx } from "../ui";
import { PlayerSearch } from "./PlayerSearch";

interface EditorProps {
  title: string;
  note: string;
  roster: Roster;
  max: number;
  excludeIds: Set<string>;
  /** League teams that can be loaded into this roster in one click. */
  teams?: ImportedTeam[];
}

function TeamPicker({ teams, onPick }: { teams: ImportedTeam[]; onPick: (t: ImportedTeam) => void }) {
  return (
    <select
      value=""
      onChange={(e) => {
        const team = teams.find((t) => String(t.team_id) === e.target.value);
        if (team) onPick(team);
      }}
      aria-label="Load a team from your league"
      className="mb-2 w-full rounded-md border border-ink-700 bg-ink-900 px-2 py-1.5 text-sm text-ink-200"
    >
      <option value="">Load a team from your league…</option>
      {teams.map((t) => (
        <option key={t.team_id} value={t.team_id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}

function RosterEditor({ title, note, roster, max, excludeIds, teams }: EditorProps) {
  const count = roster.ids.length;
  const over = count > max;
  const byPosition = POSITIONS.map((pos) => ({
    pos,
    players: roster.players
      .filter((p) => p.position === pos)
      .sort((a, b) => b.projected_ros_points - a.projected_ros_points),
  })).filter((g) => g.players.length > 0);

  return (
    <div className="flex flex-col rounded-md border border-ink-700 bg-ink-900/60 p-3">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-[11px] text-ink-500">{note}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cx("num text-xs", over ? "font-semibold text-flag-400" : "text-ink-400")}>
            {count}/{max}
          </span>
          {count > 0 && (
            <button
              onClick={roster.clear}
              aria-label={`Clear ${title}`}
              className="rounded p-1 text-ink-500 hover:bg-ink-700 hover:text-ink-100"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {teams && teams.length > 0 && <TeamPicker teams={teams} onPick={(t) => roster.replace(t.player_ids)} />}

      <PlayerSearch
        excludeIds={new Set([...roster.ids, ...excludeIds])}
        onSelect={roster.add}
        disabled={count >= max}
        disabledText="Roster is full"
        placeholder="Add a player…"
      />

      {over && (
        <p className="mt-2 text-xs text-flag-400">
          This roster is bigger than your league allows ({max}). Remove players or add bench spots in Lineup settings.
        </p>
      )}
      {roster.error && <p className="mt-2 text-xs text-flag-400">{roster.error}</p>}
      {roster.missingIds.length > 0 && (
        <div className="mt-2 rounded-md border border-amber-400/20 bg-amber-400/[0.06] p-2 text-xs text-amber-400">
          {roster.missingIds.length} saved player(s) are no longer in the projections (for example, out for the
          season).
          <button
            onClick={() => roster.missingIds.forEach(roster.remove)}
            className="ml-1 font-semibold underline underline-offset-2"
          >
            Remove them
          </button>
        </div>
      )}

      <div className="mt-3 space-y-3">
        {count === 0 && <p className="py-4 text-center text-xs text-ink-500">No players yet.</p>}
        {byPosition.map(({ pos, players }) => (
          <div key={pos}>
            <div className="label mb-1">
              {pos} · {players.length}
            </div>
            <ul className="space-y-1">
              {players.map((p) => (
                <RosterRow key={p.player_id} p={p} onRemove={() => roster.remove(p.player_id)} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function RosterRow({ p, onRemove }: { p: PlayerValue; onRemove: () => void }) {
  return (
    <li className="flex items-center gap-2.5 rounded px-2 py-1 hover:bg-ink-800">
      <PlayerAvatar player={p} size={24} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm text-ink-100">
          <span className="truncate">{p.name}</span>
          <InjuryTag status={p.injury_status} />
        </div>
      </div>
      <PositionBadge position={p.position} rank={p.positional_rank} />
      <span className="w-8 text-xs text-ink-500">{p.nfl_team}</span>
      <span className="num w-10 text-right text-xs text-ink-300">{p.projected_ros_points.toFixed(0)}</span>
      <button
        onClick={onRemove}
        aria-label={`Remove ${p.name} from roster`}
        className="rounded p-0.5 text-ink-500 hover:text-ink-100"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </li>
  );
}

interface SectionProps {
  rosterA: Roster;
  /** Omit to show only your roster (e.g. on the Moves page). */
  rosterB?: Roster;
  max: number;
  hint?: string;
}

/** Optional rosters. With them, grades measure the change in each team's optimal starting lineup. */
export function RosterSection({ rosterA, rosterB, max, hint = "add yours to see lineup impact" }: SectionProps) {
  const [open, setOpen] = useState(false);
  const summary = (r: Roster) => (r.ids.length ? `${r.ids.length} players` : "not set");
  const { league, myTeam } = useEspnLeague();
  const otherTeams = league?.teams.filter((t) => t.team_id !== myTeam?.team_id);

  return (
    <section className="card mb-4 overflow-visible">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-ink-700/60 text-ink-300">
          <Users className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-ink-100">{rosterB ? "Rosters" : "Your roster"}</div>
          <div className="truncate text-xs text-ink-400">
            {rosterB ? "Your roster: " : ""}
            <span className="text-ink-200">{summary(rosterA)}</span>
            {rosterB && (
              <>
                {" "}
                · Their roster: <span className="text-ink-200">{summary(rosterB)}</span>
              </>
            )}
            {rosterA.ids.length === 0 && <span className="hidden sm:inline"> · {hint}</span>}
          </div>
        </div>
        <span className="hidden text-xs font-medium text-ink-300 sm:inline">
          {open ? "Hide" : rosterA.ids.length ? "Edit" : rosterB ? "Add rosters" : "Add roster"}
        </span>
        <ChevronDown className={cx("h-4 w-4 text-ink-400 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className={cx("grid gap-3 border-t border-ink-700 p-4", rosterB && "md:grid-cols-2")}>
          <RosterEditor
            title={rosterB ? "Your roster (Team A)" : "Your roster"}
            note={myTeam ? `Synced from ESPN: ${myTeam.name}.` : "Saved in this browser."}
            roster={rosterA}
            max={max}
            excludeIds={new Set(rosterB?.ids ?? [])}
          />
          {rosterB && (
            <RosterEditor
              title="Their roster (Team B)"
              note="Optional. Lets the app grade their side too."
              teams={otherTeams}
              roster={rosterB}
              max={max}
              excludeIds={new Set(rosterA.ids)}
            />
          )}
        </div>
      )}
    </section>
  );
}
