import { useEffect, useState } from "react";
import { ApiError, api, leagueKey } from "../services/api";
import type { DatasetInfo, LeagueSettings, PlayerValue, Position } from "../types/api";

interface State {
  players: PlayerValue[];
  total: number;
  dataset: DatasetInfo | null;
  loading: boolean;
  error: string | null;
  /** The search text these results were fetched for (results can lag the latest input). */
  resultsFor: string | null;
}

/** Fetches players for the given league + filters; cancels stale requests when inputs change. */
export function usePlayers(
  league: LeagueSettings,
  opts: { q?: string; position?: Position; limit?: number; enabled?: boolean },
) {
  const { q, position, limit, enabled = true } = opts;
  const [state, setState] = useState<State>({
    players: [],
    total: 0,
    dataset: null,
    loading: enabled,
    error: null,
    resultsFor: null,
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    api
      .searchPlayers(league, { q, position, limit }, controller.signal)
      .then((res) =>
        setState({
          players: res.players,
          total: res.total,
          dataset: res.dataset,
          loading: false,
          error: null,
          resultsFor: q ?? "",
        }),
      )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "Something went wrong loading players.";
        setState((s) => ({ ...s, loading: false, error: message }));
      });
    return () => controller.abort();
    // Depend on the league key, not the league object, so a re-created object doesn't refetch.
  }, [leagueKey(league), q, position, limit, enabled, reloadKey]);

  return { ...state, reload: () => setReloadKey((k) => k + 1) };
}
