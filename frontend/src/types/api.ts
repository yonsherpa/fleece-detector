// Mirrors the Pydantic models in backend/app/models. Keep the two in sync.

export type Position = "QB" | "RB" | "WR" | "TE";
export const POSITIONS: Position[] = ["QB", "RB", "WR", "TE"];

export type ScoringFormat = "ppr" | "half_ppr" | "standard" | "custom";

export interface LineupSlots {
  QB: number;
  RB: number;
  WR: number;
  TE: number;
  FLEX: number;
  SUPERFLEX: number;
  BENCH: number;
}

export type SlotName = keyof LineupSlots;
export const SLOT_NAMES: SlotName[] = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "BENCH"];

// Same defaults and limits as LineupSlots in backend/app/models/league.py (ESPN standard, no K/DST).
export const DEFAULT_LINEUP: LineupSlots = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0, BENCH: 7 };
export const SLOT_LIMITS: Record<SlotName, number> = { QB: 3, RB: 4, WR: 5, TE: 3, FLEX: 3, SUPERFLEX: 2, BENCH: 12 };

export function maxRosterSize(lineup: LineupSlots): number {
  return SLOT_NAMES.reduce((sum, slot) => sum + lineup[slot], 0);
}

export interface LeagueSettings {
  num_teams: number;
  scoring_format: ScoringFormat;
  lineup: LineupSlots;
  /** Present when scoring_format is "custom" (e.g. imported from ESPN). */
  scoring?: ScoringSettings | null;
}

export interface DatasetInfo {
  source: string;
  is_sample: boolean;
  as_of: string;
  season: number | null;
  week: number | null;
  description: string;
}

export interface PlayerValue {
  player_id: string;
  name: string;
  position: Position;
  nfl_team: string;
  bye_week: number | null;
  injury_status: string | null;
  games_remaining: number;
  projection_available: boolean;
  projected_ppg: number | null;
  projected_ros_points: number;
  replacement_ros_points: number;
  value_over_replacement: number;
  positional_rank: number | null;
}

export interface PlayerListResponse {
  players: PlayerValue[];
  total: number;
  dataset: DatasetInfo;
}

export interface TradeRequest {
  team_a_gives: string[];
  team_a_receives: string[];
  team_a_roster?: string[] | null;
  team_b_roster?: string[] | null;
  league: LeagueSettings;
}

export type GradeMethod = "roster_aware" | "value_only";
export type Side = "team_a" | "team_b" | "even";

export interface LineupSlotAssignment {
  slot: string;
  player_id: string;
  name: string;
  position: Position;
  projected_ros_points: number;
  is_replacement: boolean;
}

export interface LineupSnapshot {
  total_points: number;
  starters: LineupSlotAssignment[];
  bench: LineupSlotAssignment[];
}

export interface PositionImpact {
  position: Position;
  starter_points_before: number;
  starter_points_after: number;
  starter_points_delta: number;
  roster_count_before: number;
  roster_count_after: number;
  top_backup_points_before: number | null;
  top_backup_points_after: number | null;
}

export interface RosterImpact {
  lineup_before: LineupSnapshot;
  lineup_after: LineupSnapshot;
  lineup_delta: number;
  lineup_delta_pct: number;
  positions: PositionImpact[];
  dropped_players: string[];
  replacements_added: Position[];
}

export interface TeamImpact {
  grade: string;
  grade_method: GradeMethod;
  grade_score: number;
  value_given: number;
  value_received: number;
  net_value: number;
  roster: RosterImpact | null;
}

export interface TradeEvaluation {
  grade: string;
  winner: Side;
  winner_basis: GradeMethod;
  fairness: { score: number; label: string; favored: Side };
  team_a: TeamImpact;
  team_b: TeamImpact;
  players_given: PlayerValue[];
  players_received: PlayerValue[];
  explanation: { summary: string; details: string[] };
  warnings: string[];
  league: LeagueSettings;
  dataset: DatasetInfo;
}

export interface HealthResponse {
  status: string;
  players_loaded: number;
  dataset: DatasetInfo;
}

export interface MoveSuggestion {
  player: PlayerValue;
  /** Points your best lineup gains (+) or loses (-); null when no roster was sent. */
  lineup_change: number | null;
  drop_to_make_room: string | null;
  trend_count: number | null;
  on_your_roster: boolean;
  owner_team: string | null;
  reason: string;
}

export interface MovesResponse {
  has_roster: boolean;
  sell_high: MoveSuggestion[];
  safe_to_drop: MoveSuggestion[];
  trending_adds: MoveSuggestion[];
  trending_drops: MoveSuggestion[];
  waiver_targets: MoveSuggestion[];
  buy_targets: MoveSuggestion[];
  buy_budget: number | null;
  rostered_cutoff: number;
  availability: "league" | "estimated";
  trending: {
    available: boolean;
    message: string | null;
    lookback_hours: number;
    fetched_at: string | null;
    unprojected_count: number;
  };
  notes: string[];
  league: LeagueSettings;
  dataset: DatasetInfo;
}

export interface ScoringSettings {
  pass_yd: number;
  pass_td: number;
  pass_int: number;
  rush_yd: number;
  rush_td: number;
  reception: number;
  rec_yd: number;
  rec_td: number;
  fumble_lost: number;
  te_reception_bonus: number;
  two_pt_conversion: number;
}

export interface ImportedPlayer {
  espn_id: number;
  name: string;
  position: string;
  nfl_team: string | null;
  lineup_slot: string;
  player_id: string | null;
  match_method: "espn_id" | "name_position" | "name" | null;
}

export interface ImportedTeam {
  team_id: number;
  name: string;
  abbrev: string;
  players: ImportedPlayer[];
  player_ids: string[];
}

export interface LeagueImport {
  league_id: number;
  season: number;
  name: string;
  size: number;
  current_week: number | null;
  league_settings: LeagueSettings;
  scoring_summary: string[];
  teams: ImportedTeam[];
  matched_count: number;
  unmatched: string[];
  unsupported_count: number;
  notes: string[];
  fetched_at: string;
}
