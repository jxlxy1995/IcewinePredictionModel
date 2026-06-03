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
  home_team_logo_url?: string | null;
  away_team_name: string;
  away_team_display_name?: string;
  away_team_logo_url?: string | null;
  home_score?: number | null;
  away_score?: number | null;
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

export type TrainingFileStatus = {
  exists: boolean;
  path: string;
  updated_at: string | null;
  size_bytes: number;
};

export type TrainingDatasetStatus = TrainingFileStatus & {
  row_count: number;
  column_count: number;
};

export type TrainingQaStatus = {
  exists: boolean;
  path: string;
  updated_at: string | null;
  empty_required_cells: number;
  invalid_odds_cells: number;
  invalid_probability_cells: number;
  invalid_overround_cells: number;
  thin_history_count: number;
  thin_history_ratio: string;
  low_sample_leagues: Record<string, number>;
};

export type TrainingMarketBaselineMetric = {
  evaluated_count: number;
  skipped_count: number;
  accuracy: string;
  log_loss: string;
  brier: string;
  overround: string;
  flat_bet_profit_units: string;
  flat_bet_roi: string;
  predicted_side_counts: Record<string, number>;
};

export type TrainingMarketBaselineStatus = {
  exists: boolean;
  path: string;
  updated_at: string | null;
  market_samples: number;
  evaluated_market_samples: number;
  skipped_market_samples: number;
  market_reports: Record<string, TrainingMarketBaselineMetric>;
};

export type TrainingRunStatus = "running" | "success" | "failed";

export type TrainingRunStep =
  | "queued"
  | "baseline_dataset"
  | "dataset_qa"
  | "market_baseline"
  | "feature_set"
  | "dynamic_feature_set"
  | "away_cover_stability"
  | "away_cover_bucket_threshold_v2"
  | "away_cover_bucket_sandbox_v2"
  | "total_goals_edge_stability_v1"
  | "total_goals_bucket_sandbox_v2"
  | "finalize";

export type TrainingRun = {
  id: number;
  run_type: string;
  status: TrainingRunStatus;
  started_at: string;
  finished_at: string | null;
  snapshot_tag: string;
  current_step: TrainingRunStep | string | null;
  error_step: TrainingRunStep | string | null;
  error_message: string | null;
  dataset_rows: number | null;
  eligible_matches: number | null;
  complete_matches: number | null;
  coverage_ratio: string | null;
  last_trained_match_id: number | null;
  last_trained_match_summary: string | null;
  last_trained_kickoff_time: string | null;
  new_complete_matches: number | null;
  artifact_paths: Record<string, string | null>;
};

export type TrainingWorkspace = {
  dataset: TrainingDatasetStatus;
  dataset_report: TrainingFileStatus;
  qa: TrainingQaStatus;
  market_baseline: TrainingMarketBaselineStatus;
  latest_run: TrainingRun | null;
};

export type PaperStrategy = {
  strategy_key: string;
  display_name: string;
  market_type: string;
  side: string | null;
  edge_threshold: string;
  model_name: string;
  signal_version: string | null;
};

export type PaperCandidate = {
  match_id: number;
  source_match_id: string | null;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  status: string;
  market_type: string;
  side: string | null;
  recommended_handicap: string | null;
  line: string | null;
  odds: string | null;
  model_probability: string | null;
  market_probability: string | null;
  edge: string | null;
  line_bucket: string;
  risk_tags: string[];
  strategy_key: string;
  strategy_display_name: string;
  signal_version: string | null;
  odds_source: string;
  execution_target: string | null;
  historical_snapshot_count: number;
  robustness_mode: string | null;
  robustness_status: string | null;
  robustness_primary_target: number | null;
  robustness_seen_count: number | null;
  robustness_min_edge: string | null;
  robustness_observed_targets: number[];
  is_recordable: boolean;
};

export type PaperRecord = {
  id: number;
  match_id: number;
  source_match_id: string | null;
  created_at: string;
  updated_at: string;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  home_team_logo_url?: string | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  away_team_logo_url?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  strategy_key: string;
  strategy_display_name: string;
  model_name: string;
  signal_version: string | null;
  market_type: string;
  side: string;
  recommended_handicap: string | null;
  original_recommended_handicap: string | null;
  line_bucket: string | null;
  risk_tags: string[];
  original_market_line: string;
  original_odds: string;
  current_market_line: string;
  current_odds: string;
  model_probability: string | null;
  market_probability: string | null;
  edge: string;
  stake_units: string;
  status: string;
  is_manually_adjusted: boolean;
  manual_note: string | null;
  settlement_result: string | null;
  profit_units: string | null;
  settled_at: string | null;
};

export type PaperSummary = {
  total_records: number;
  pending_records: number;
  settled_records: number;
  void_records: number;
  candidate_count: number;
  total_stake_units: string;
  total_profit_units: string;
  hit_rate: string;
  roi: string;
};

export type PaperGroupSummary = {
  group_name: string;
  record_count: number;
  settled_records: number;
  total_stake_units: string;
  total_profit_units: string;
  hit_rate: string;
  roi: string;
};

export type PaperConfidenceSimulationGroup = {
  group_key: string;
  match_id: number;
  source_match_id: string | null;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  home_team_logo_url?: string | null;
  home_score?: number | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  away_team_logo_url?: string | null;
  away_score?: number | null;
  market_type: string;
  logical_side: string;
  recommendation_text: string | null;
  representative_record_id: number;
  representative_strategy_key: string;
  representative_market_line: string;
  representative_odds: string;
  signal_record_ids: number[];
  triggered_strategy_keys: string[];
  triggered_strategy_display_names: string[];
  signal_families: string[];
  confidence_score: number;
  suggested_stake_units: string;
  stake_cap_reason: string;
  status: string;
  settlement_result: string | null;
  flat_profit_units: string;
  weighted_profit_units: string;
  warning: string | null;
};

export type PaperConfidenceSimulationSummary = {
  group_count: number;
  settled_groups: number;
  suggested_stake_units: string;
  flat_profit_units: string;
  weighted_profit_units: string;
  flat_roi: string;
  weighted_roi: string;
};

export type PaperConfidenceSimulationGroupSummary = {
  group_name: string;
  group_count: number;
  settled_groups: number;
  suggested_stake_units: string;
  flat_profit_units: string;
  weighted_profit_units: string;
  flat_roi: string;
  weighted_roi: string;
};

export type PaperConfidenceSimulationWorkspace = {
  summary: PaperConfidenceSimulationSummary;
  groups: PaperConfidenceSimulationGroup[];
  by_score_bucket: PaperConfidenceSimulationGroupSummary[];
  by_stake_bucket: PaperConfidenceSimulationGroupSummary[];
  by_family_combo: PaperConfidenceSimulationGroupSummary[];
};

export type PaperBatchRecordSkippedItem = {
  match_id: number | null;
  strategy_key: string | null;
  reason: string;
};

export type PaperBatchRecordResult = {
  requested_count: number;
  created_count: number;
  skipped_count: number;
  skipped: PaperBatchRecordSkippedItem[];
};

export type PaperRecommendationDiagnostics = {
  total_matches: number;
  candidate_count: number;
  candidate_match_count: number;
  status_counts: Record<string, number>;
  edge_threshold: string;
};

export type PaperRecommendationWorkspace = {
  strategies: PaperStrategy[];
  candidates: PaperCandidate[];
  records: PaperRecord[];
  summary: PaperSummary;
  groups: {
    by_strategy: PaperGroupSummary[];
    by_league: PaperGroupSummary[];
    by_line_bucket: PaperGroupSummary[];
    by_manual_adjustment: PaperGroupSummary[];
  };
  confidence_simulation?: PaperConfidenceSimulationWorkspace;
  diagnostics?: PaperRecommendationDiagnostics;
  batch_result?: PaperBatchRecordResult;
};

export type DataSyncFreshness = {
  latest_fixtures_results_sync: string | null;
  latest_odds_sync: string | null;
  latest_kickoff_time: string | null;
  latest_odds_snapshot_time: string | null;
};

export type MatchListLeagueOption = {
  name: string;
  display_name: string;
};

export type MatchListFilters = {
  start_time: string;
  end_time: string;
  league_name: string | null;
  status_filter: string;
  odds_filter: string | string[];
  search: string | null;
};

export type MatchOddsSummary = {
  asian_handicap: string | null;
  total_goals: string | null;
  match_winner: string | null;
};

export type MatchListMatch = {
  match_id: number;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  home_team_logo_url?: string | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  away_team_logo_url?: string | null;
  status: string;
  status_group: string;
  home_score: number | null;
  away_score: number | null;
  has_odds: boolean;
  odds_status_key: string;
  odds_status_label: string;
  odds_summary: MatchOddsSummary;
};

export type MatchListWorkspace = {
  filters: MatchListFilters;
  freshness: DataSyncFreshness;
  leagues: MatchListLeagueOption[];
  total_matches: number;
  matches: MatchListMatch[];
};

export type RecommendationSummaryPlaceholder = {
  count: number;
  label: string;
};

export type MatchDetail = MatchListMatch & {
  team_data_note: string;
  paper_recommendation_summary: RecommendationSummaryPlaceholder;
  formal_recommendation_summary: RecommendationSummaryPlaceholder;
};

export type DataSyncRun = {
  id: number;
  sync_type: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  days: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  requests_used: number;
  error_message: string | null;
};

export type MatchSyncItem = {
  match_id: number;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  fixture: string;
  status: string;
  message: string;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  requests_used: number;
  source_fixture_id?: string | null;
  diagnostic_status?: string | null;
  diagnostic_error?: string | null;
  snapshot_count: number;
};

export type MatchSyncReport = {
  sync_type: string;
  started_at: string;
  finished_at: string | null;
  target_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  requests_used: number;
  created_count?: number;
  updated_count?: number;
  success: MatchSyncItem[];
  failed: MatchSyncItem[];
  skipped: MatchSyncItem[];
};

export type MatchSyncResponse = {
  sync_run: DataSyncRun;
  report: MatchSyncReport;
};

export type MatchSyncRunDetail = MatchSyncResponse;

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
  trainingWorkspace: TrainingWorkspace;
  paperRecommendations: PaperRecommendationWorkspace;
  matchList: MatchListWorkspace;
  source: "api" | "mock";
};
