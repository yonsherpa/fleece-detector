import { useEffect, useMemo, useState } from "react";
import { ApiError, api, leagueKey } from "../services/api";
import type { LeagueSettings, PlayerValue } from "../types/api";

function loadIds(storageKey: string | null): string[] {
  if (!storageKey) return [];
  try {
    const raw = localStorage.getItem(storageKey);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/**
 * A roster is a list of player ids. Values are re-fetched whenever the roster or the
 * league settings change, because a player's value depends on both.
 * Pass a storageKey to remember the roster in this browser (localStorage).
 */
export function useRoster(league: LeagueSettings, storageKey: string | null = null) {
  const [ids, setIds] = useState<string[]>(() => loadIds(storageKey));
  const [values, setValues] = useState<Record<string, PlayerValue>>({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(ids));
    } catch {
      /* storage unavailable: the roster still works for this visit */
    }
  }, [ids, storageKey]);

  // Another part of the app (the ESPN import) can replace a saved roster while this page is open.
  useEffect(() => {
    if (!storageKey) return;
    const onSync = (e: Event) => {
      const detail = (e as CustomEvent<{ key: string; ids: string[] }>).detail;
      if (detail.key === storageKey) setIds(detail.ids);
    };
    window.addEventListener(ROSTER_SYNC_EVENT, onSync);
    return () => window.removeEventListener(ROSTER_SYNC_EVENT, onSync);
  }, [storageKey]);

  const key = `${leagueKey(league)}#${ids.join(",")}`;
  useEffect(() => {
    if (ids.length === 0) {
      setLoaded(true);
      return;
    }
    let cancelled = false;
    setError(null);
    api
      .playersByIds(ids, league)
      .then((res) => {
        if (cancelled) return;
        setValues(Object.fromEntries(res.players.map((p) => [p.player_id, p])));
        setLoaded(true);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load roster values.");
      });
    return () => {
      cancelled = true;
    };
    // `key` covers both ids and league, so the effect re-runs exactly when either changes.
  }, [key]);

  const players = useMemo(() => ids.map((id) => values[id]).filter((p): p is PlayerValue => !!p), [ids, values]);
  // Only report missing ids once a lookup has finished, so newly added players don't flash as "missing".
  const missingIds = loaded && !error ? ids.filter((id) => !values[id]) : [];

  return {
    ids,
    players,
    missingIds,
    error,
    add: (p: PlayerValue) => {
      setValues((v) => ({ ...v, [p.player_id]: p }));
      setIds((list) => (list.includes(p.player_id) ? list : [...list, p.player_id]));
    },
    remove: (id: string) => setIds((list) => list.filter((x) => x !== id)),
    clear: () => setIds([]),
    replace: (next: string[]) => setIds([...new Set(next)]),
  };
}

export const MY_ROSTER_KEY = "fleece-detector.roster-a";
const ROSTER_SYNC_EVENT = "fleece-detector:roster-sync";

/** Save a roster and tell any open page using the same key to pick it up. */
export function saveRoster(storageKey: string, ids: string[]) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(ids));
  } catch {
    /* ignore: open pages still get the event below */
  }
  window.dispatchEvent(new CustomEvent(ROSTER_SYNC_EVENT, { detail: { key: storageKey, ids } }));
}

export type Roster = ReturnType<typeof useRoster>;
