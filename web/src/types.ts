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

export type OddspapiWorkerProgressAudit = {
  status: string | null;
  mode: string | null;
  season: number | null;
  updated_at: string | null;
  current_league_id: string | null;
  current_league_name: string | null;
  current_league_display_name: string | null;
  round: number | null;
  processed_matches: number | null;
  inserted_snapshots: number | null;
  failed_matches: number | null;
  requests_used: number | null;
  total_processed_matches: number | null;
  total_inserted_snapshots: number | null;
  total_failed_matches: number | null;
  total_requests_used: number | null;
};

export type OddspapiLeagueBackfillAudit = {
  league_name: string;
  league_display_name?: string;
  source_league_id: string | null;
  finished_matches: number;
  matched_matches: number;
  snapshot_matches: number;
  snapshot_count: number;
  asian_handicap_snapshot_count: number;
  total_goals_snapshot_count: number;
  status_counts: Record<string, number>;
  error_counts: Record<string, number>;
};

export type OddspapiBackfillAudit = {
  season: number;
  log_dir: string;
  worker_progress: OddspapiWorkerProgressAudit | null;
  league_summaries: OddspapiLeagueBackfillAudit[];
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
  draw_odds?: string;
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
  match_winner: OddsPoint[];
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

export type ModelTrainingStatus = "ready" | "training" | "failed";

export type ModelTrainingRun = {
  model_name: string;
  model_version: string;
  status: ModelTrainingStatus;
  trained_at: string;
  sample_count: number;
  league_count: number;
  market_types: string[];
  validation_log_loss: string | null;
  validation_brier_score: string | null;
};

export type ModelLeagueTrainingCoverage = {
  league_name: string;
  league_display_name?: string;
  season: number;
  finished_matches: number;
  training_matches: number;
  coverage_ratio: string;
};

export type ModelTrainingOverview = {
  generated_at: string;
  total_training_matches: number;
  total_training_snapshots: number;
  model_runs: ModelTrainingRun[];
  league_training_coverage: ModelLeagueTrainingCoverage[];
};

export type DashboardData = {
  summary: DashboardSummary;
  leagues: LeagueCoverage[];
  workers: WorkerStatus[];
  oddspapiBackfillAudit: OddspapiBackfillAudit;
  unmatched: UnmatchedMatch[];
  oddsTrends: MatchOddsTrends;
  matchesWithOdds: MatchWithOdds[];
  missingTeamDisplayNames: TeamDisplayNameRow[];
  doneDisplayTranslationKeys: string[];
  recommendationRecords: RecommendationRecord[];
  modelTraining: ModelTrainingOverview;
  source: "api" | "mock";
};
