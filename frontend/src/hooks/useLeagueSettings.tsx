import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { DEFAULT_LINEUP, type LeagueSettings } from "../types/api";

const STORAGE_KEY = "fleece-detector.league";
const DEFAULT_LEAGUE: LeagueSettings = { num_teams: 12, scoring_format: "ppr", lineup: DEFAULT_LINEUP };

function loadInitial(): LeagueSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Partial<LeagueSettings>;
      return { ...DEFAULT_LEAGUE, ...saved, lineup: { ...DEFAULT_LINEUP, ...saved.lineup } };
    }
  } catch {
    /* storage unavailable or corrupt: fall back to defaults */
  }
  return DEFAULT_LEAGUE;
}

interface Ctx {
  league: LeagueSettings;
  setLeague: (update: Partial<LeagueSettings>) => void;
}

const LeagueContext = createContext<Ctx | null>(null);

/** League settings shared by every page (values depend on scoring + league size). */
export function LeagueProvider({ children }: { children: ReactNode }) {
  const [league, setLeagueState] = useState<LeagueSettings>(loadInitial);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(league));
    } catch {
      /* ignore */
    }
  }, [league]);

  const setLeague = (update: Partial<LeagueSettings>) => setLeagueState((l) => ({ ...l, ...update }));
  return <LeagueContext.Provider value={{ league, setLeague }}>{children}</LeagueContext.Provider>;
}

export function useLeague(): Ctx {
  const ctx = useContext(LeagueContext);
  if (!ctx) throw new Error("useLeague must be used inside <LeagueProvider>");
  return ctx;
}
