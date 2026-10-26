import {
  SLOT_NAMES,
  type HealthResponse,
  type LeagueImport,
  type LeagueSettings,
  type LineupSlots,
  type MovesResponse,
  type PlayerListResponse,
  type PlayerValue,
  type Position,
  type ScoringSettings,
  type TradeEvaluation,
  type TradeRequest,
} from "../types/api";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** An error the UI can show directly: a readable message plus the HTTP status (0 = unreachable). */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(`Can't reach the Fleece Detector API at ${BASE_URL}. Is the backend running?`, 0);
  }

  if (res.ok) return (await res.json()) as T;

  // Backend domain errors: {"error": {"code", "message"}}. Pydantic errors: {"detail": [...]}.
  const body = await res.json().catch(() => null);
  if (body?.error?.message) throw new ApiError(body.error.message, res.status, body.error.code);
  if (Array.isArray(body?.detail)) {
    const first = body.detail[0];
    throw new ApiError(`Invalid request: ${first?.msg ?? "validation failed"}`, res.status, "validation");
  }
  throw new ApiError(`Request failed (${res.status})`, res.status);
}

function leagueQuery(league: LeagueSettings): Record<string, string> {
  const query: Record<string, string> = {
    scoring_format: league.scoring_format,
    num_teams: String(league.num_teams),
    lineup: lineupParam(league.lineup),
  };
  if (league.scoring_format === "custom" && league.scoring) query.scoring = scoringParam(league.scoring);
  return query;
}

/** Same format the backend parses: "QB:1,RB:2,...". */
export function lineupParam(lineup: LineupSlots): string {
  return SLOT_NAMES.map((slot) => `${slot}:${lineup[slot]}`).join(",");
}

/** Custom scoring as "field:points,..." for GET requests. */
function scoringParam(scoring: ScoringSettings): string {
  return Object.entries(scoring)
    .map(([field, points]) => `${field}:${points}`)
    .join(",");
}

/** Stable key for effects that should re-run when any league setting changes. */
export function leagueKey(league: LeagueSettings): string {
  const custom = league.scoring_format === "custom" && league.scoring ? scoringParam(league.scoring) : "";
  return `${league.scoring_format}|${custom}|${league.num_teams}|${lineupParam(league.lineup)}`;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  searchPlayers: (
    league: LeagueSettings,
    opts: { q?: string; position?: Position; limit?: number } = {},
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams(leagueQuery(league));
    if (opts.q) params.set("q", opts.q);
    if (opts.position) params.set("position", opts.position);
    params.set("limit", String(opts.limit ?? 50));
    return request<PlayerListResponse>(`/players?${params}`, { signal });
  },

  /** Values for a list of ids (e.g. a saved roster). Ids no longer in the dataset are simply absent. */
  playersByIds: (ids: string[], league: LeagueSettings) => {
    const params = new URLSearchParams(leagueQuery(league));
    params.set("ids", ids.join(","));
    params.set("limit", "500");
    return request<PlayerListResponse>(`/players?${params}`);
  },

  getPlayer: (id: string, league: LeagueSettings) =>
    request<PlayerValue>(`/players/${encodeURIComponent(id)}?${new URLSearchParams(leagueQuery(league))}`),

  moves: (
    roster: string[] | null,
    league: LeagueSettings,
    leagueRosters: { team_name: string; player_ids: string[] }[] | null = null,
  ) =>
    request<MovesResponse>("/moves", {
      method: "POST",
      body: JSON.stringify({ roster, league, league_rosters: leagueRosters }),
    }),

  importLeague: (leagueId: number, season?: number) =>
    request<LeagueImport>(`/leagues/${leagueId}${season ? `?season=${season}` : ""}`),

  evaluateTrade: (body: TradeRequest) =>
    request<TradeEvaluation>("/trades/evaluate", { method: "POST", body: JSON.stringify(body) }),
};
