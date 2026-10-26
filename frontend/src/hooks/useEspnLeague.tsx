import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api } from "../services/api";
import type { ImportedTeam, LeagueImport } from "../types/api";
import { useLeague } from "./useLeagueSettings";
import { MY_ROSTER_KEY, saveRoster } from "./useRoster";

const STORAGE_KEY = "fleece-detector.espn";

interface Saved {
  leagueId: number;
  myTeamId: number | null;
}

function loadSaved(): Saved | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

function persist(saved: Saved | null) {
  try {
    if (saved) localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable: the connection lasts for this visit */
  }
}

interface Ctx {
  league: LeagueImport | null;
  myTeam: ImportedTeam | null;
  loading: boolean;
  error: string | null;
  connect: (leagueId: number, teamId?: number | null) => Promise<boolean>;
  refresh: () => void;
  chooseMyTeam: (teamId: number) => void;
  applySettings: () => void;
  disconnect: () => void;
}

const EspnContext = createContext<Ctx | null>(null);

/**
 * The imported ESPN league, shared by every page. Only the league id and "which team is mine"
 * are saved; rosters are re-fetched from ESPN so they follow real adds, drops and trades.
 */
export function EspnLeagueProvider({ children }: { children: ReactNode }) {
  const { setLeague } = useLeague();
  const [saved, setSaved] = useState<Saved | null>(loadSaved);
  const [league, setLeagueData] = useState<LeagueImport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const myTeam = league?.teams.find((t) => t.team_id === saved?.myTeamId) ?? null;

  const load = useCallback(async (leagueId: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.importLeague(leagueId);
      setLeagueData(data);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't import that league.");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // On app load, refresh a saved league so "my roster" follows what happened on ESPN since.
  useEffect(() => {
    if (saved) load(saved.leagueId);
    // Only on first load; later refreshes are explicit.
  }, []);

  // Keep the saved roster synced with my ESPN team whenever fresh league data arrives.
  useEffect(() => {
    if (myTeam) saveRoster(MY_ROSTER_KEY, myTeam.player_ids);
  }, [league, myTeam?.team_id]);

  const value: Ctx = {
    league,
    myTeam,
    loading,
    error,
    connect: async (leagueId, teamId) => {
      const data = await load(leagueId);
      if (!data) return false;
      // A pasted team URL (…&teamId=1) already says which team is yours.
      const known = teamId != null && data.teams.some((t) => t.team_id === teamId);
      const next = { leagueId, myTeamId: known ? teamId : null };
      setSaved(next);
      persist(next);
      setLeague(data.league_settings); // scoring, size and lineup now match the real league
      return true;
    },
    refresh: () => saved && load(saved.leagueId),
    chooseMyTeam: (teamId) => {
      if (!saved) return;
      const next = { ...saved, myTeamId: teamId };
      setSaved(next);
      persist(next);
    },
    applySettings: () => league && setLeague(league.league_settings),
    disconnect: () => {
      setSaved(null);
      persist(null);
      setLeagueData(null);
      setError(null);
    },
  };
  return <EspnContext.Provider value={value}>{children}</EspnContext.Provider>;
}

export function useEspnLeague(): Ctx {
  const ctx = useContext(EspnContext);
  if (!ctx) throw new Error("useEspnLeague must be used inside <EspnLeagueProvider>");
  return ctx;
}
