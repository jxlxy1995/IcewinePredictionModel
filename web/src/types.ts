export type DashboardSummary = {
  total_matches: number;
  finished_matches: number;
  matches_with_historical_odds: number;
  historical_odds_snapshots: number;
  unmatched_matches: number;
};

export type LeagueCoverage = {
  league_id: number;
  league_name: string;
  league_display_name?: string;
  country_or_region: string;
  season: number;
  finished_matches: number;
  matches_with_historical_odds: number;
  coverage_ratio: string;
  unmatched_matches: number;
};

export type WorkerStatus = {
  pid: number;
  started_at?: string;
  status: string;
  runtime_status: "running" | "stopped" | string;
  mode: string | null;
  season: number | null;
  league_ids: string[];
  process_log_path: string | null;
  worker_log_dir?: string | null;
  notify_on_complete: boolean;
};

export type UnmatchedMatch = {
  match_id: number;
  league_name: string;
  league_display_name?: string;
  home_team_name: string;
  home_team_display_name?: string;
  away_team_name: string;
  away_team_display_name?: string;
  kickoff_time: string;
  source_name?: string;
  match_reason: string;
  historical_odds_error?: string | null;
  alias_candidates?: string[];
};

export type OddsPoint = {
  snapshot_time: string;
  bookmaker: string;
  market_line: string;
  home_odds?: string;
  away_odds?: string;
  over_odds?: string;
  under_odds?: string;
};

export type MatchOddsTrends = {
  match_id: number;
  league_name: string;
  league_display_name?: string;
  home_team_name: string;
  home_team_display_name?: string;
  away_team_name: string;
  away_team_display_name?: string;
  kickoff_time: string;
  asian_handicap: OddsPoint[];
  total_goals: OddsPoint[];
};

export type MatchWithOdds = {
  match_id: number;
  league_name: string;
  league_display_name?: string;
  home_team_name: string;
  home_team_display_name?: string;
  away_team_name: string;
  away_team_display_name?: string;
  kickoff_time: string;
  snapshot_count: number;
};

export type RecommendationRecord = {
  id: number;
  match_id: number;
  league_name: string;
  league_display_name?: string;
  home_team_name: string;
  home_team_display_name?: string;
  away_team_name: string;
  away_team_display_name?: string;
  kickoff_time: string;
  market_type: string;
  side: string;
  market_line: string;
  odds: string;
  confidence_grade: string;
  stake_units: string;
  status: string;
  settlement_result: string | null;
  profit_units: string | null;
};

export type TeamDisplayNameRow = {
  league_id: number;
  league_name: string;
  league_display_name?: string;
  season: number | null;
  team_id: number;
  team_name: string;
  team_display_name?: string | null;
  team_logo_url?: string | null;
  is_missing_display_name?: boolean;
  match_count: number;
  latest_kickoff_time: string | null;
  rank?: number | null;
  points?: number | null;
};

export type TeamDisplayNameWorkspace = {
  league_id: number;
  league_name: string;
  league_display_name?: string;
  season: number;
  is_translation_done: boolean;
  teams: TeamDisplayNameRow[];
};

export type DisplayTranslationStatus = {
  done_league_seasons: string[];
};

export type DashboardData = {
  summary: DashboardSummary;
  leagues: LeagueCoverage[];
  workers: WorkerStatus[];
  unmatched: UnmatchedMatch[];
  oddsTrends: MatchOddsTrends;
  matchesWithOdds: MatchWithOdds[];
  missingTeamDisplayNames: TeamDisplayNameRow[];
  doneDisplayTranslationKeys: string[];
  recommendationRecords: RecommendationRecord[];
  source: "api" | "mock";
};
