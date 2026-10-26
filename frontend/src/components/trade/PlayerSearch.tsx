import { Loader2, Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useDebounce } from "../../hooks/useDebounce";
import { useLeague } from "../../hooks/useLeagueSettings";
import { usePlayers } from "../../hooks/usePlayers";
import type { PlayerValue } from "../../types/api";
import { PlayerIdentity, cx, fmt } from "../ui";

interface Props {
  excludeIds: Set<string>;
  onSelect: (player: PlayerValue) => void;
  disabled?: boolean;
  disabledText?: string;
  placeholder?: string;
  /** Pick only from these players (e.g. a roster) instead of searching the whole league. */
  pool?: PlayerValue[];
}

function matchesQuery(p: PlayerValue, q: string): boolean {
  const query = q.toLowerCase();
  return !query || p.name.toLowerCase().includes(query) || p.nfl_team.toLowerCase() === query || p.position.toLowerCase() === query;
}

/** Autocomplete over GET /players (or a local pool). Keyboard: ↑ ↓ to move, Enter to add, Esc to close. */
export function PlayerSearch({
  excludeIds,
  onSelect,
  disabled,
  disabledText = "Maximum players added",
  placeholder = "Search players or team…",
  pool,
}: Props) {
  const { league } = useLeague();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounced = useDebounce(query.trim(), 180);
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  const remote = usePlayers(league, { q: debounced, limit: 40, enabled: open && !pool });
  const { players, loading, error } = pool
    ? {
        players: [...pool].filter((p) => matchesQuery(p, debounced)).sort((a, b) => b.value_over_replacement - a.value_over_replacement),
        loading: false,
        error: null,
      }
    : remote;
  const options = players.filter((p) => !excludeIds.has(p.player_id)).slice(0, pool ? 20 : 8);

  useEffect(() => setActive(0), [debounced]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const choose = (p: PlayerValue) => {
    onSelect(p);
    setQuery("");
    setActive(0);
  };

  // Results lag the input (debounce + network). If Enter comes first, remember it and
  // pick the top match as soon as results for the typed text arrive.
  // `resultsFor` (not `loading`) is the reliable check: for one render after the text settles,
  // the old results are still on screen before the new request has even started.
  const settled = debounced === query.trim() && (pool ? true : remote.resultsFor === debounced && !loading);
  const [pendingEnter, setPendingEnter] = useState(false);
  useEffect(() => {
    if (!pendingEnter || !settled) return;
    setPendingEnter(false);
    if (options[0]) choose(options[0]);
    // Runs when results settle; `options` and `choose` come from the same render.
  }, [pendingEnter, settled]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && query.trim() && !settled) {
      e.preventDefault();
      setPendingEnter(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && open && options[active]) {
      e.preventDefault();
      choose(options[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          value={query}
          disabled={disabled}
          placeholder={disabled ? disabledText : placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setPendingEnter(false);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="w-full rounded-md border border-ink-700 bg-ink-900 py-2 pl-9 pr-9 text-sm text-ink-100 placeholder:text-ink-500 transition-colors focus:border-mint-500/60 disabled:opacity-50"
        />
        {loading && open && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ink-500" />
        )}
      </div>

      {open && !disabled && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-80 w-full animate-rise overflow-auto rounded-md border border-ink-700 bg-ink-850 p-1 shadow-xl shadow-black/40"
        >
          {error && <li className="px-3 py-3 text-sm text-flag-400">{error}</li>}
          {!error && !loading && options.length === 0 && (
            <li className="px-3 py-3 text-sm text-ink-400">
              {pool && pool.length === 0 ? "Add players to this roster first." : debounced ? `No players match “${debounced}”.` : "No more players to add."}
            </li>
          )}
          {options.map((p, i) => (
            <li
              key={p.player_id}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(p);
              }}
              className={cx(
                "flex cursor-pointer items-center gap-3 rounded px-2 py-1.5",
                i === active ? "bg-ink-700" : "hover:bg-ink-800",
              )}
            >
              <PlayerIdentity p={p} size={30} />
              <div className="text-right">
                <div className="num text-sm text-ink-100">{fmt(p.value_over_replacement)}</div>
                <div className="text-[10px] text-ink-500">value</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
