import type {
  DashboardData,
  MatchDetail,
  MatchListWorkspace,
  MatchOddsTrends,
  OddspapiBackfillAudit,
  PaperRecommendationWorkspace,
  TeamDisplayNameWorkspace,
  TrainingWorkspace
} from "./types";

export const mockOddsTrends: MatchOddsTrends = {
  match_id: 1001,
  league_name: "英冠",
  home_team_name: "Cardiff",
  away_team_name: "Swansea",
  kickoff_time: "2026-05-20T22:00:00+08:00",
  asian_handicap: [
    {
      snapshot_time: "12:00",
      bookmaker: "pinnacle",
      market_line: "-0.25",
      home_odds: "1.930",
      away_odds: "1.950"
    },
    {
      snapshot_time: "16:00",
      bookmaker: "pinnacle",
      market_line: "-0.25",
      home_odds: "1.890",
      away_odds: "1.990"
    },
    {
      snapshot_time: "20:00",
      bookmaker: "pinnacle",
      market_line: "-0.50",
      home_odds: "2.040",
      away_odds: "1.840"
    }
  ],
  total_goals: [
    {
      snapshot_time: "12:00",
      bookmaker: "pinnacle",
      market_line: "2.50",
      over_odds: "1.910",
      under_odds: "1.970"
    },
    {
      snapshot_time: "16:00",
      bookmaker: "pinnacle",
      market_line: "2.50",
      over_odds: "1.860",
      under_odds: "2.020"
    },
    {
      snapshot_time: "20:00",
      bookmaker: "pinnacle",
      market_line: "2.75",
      over_odds: "2.010",
      under_odds: "1.870"
    }
  ],
  match_winner: [
    {
      snapshot_time: "12:00",
      bookmaker: "pinnacle",
      market_line: "0.00",
      home_odds: "2.100",
      draw_odds: "3.250",
      away_odds: "3.400"
    },
    {
      snapshot_time: "16:00",
      bookmaker: "pinnacle",
      market_line: "0.00",
      home_odds: "2.000",
      draw_odds: "3.300",
      away_odds: "3.650"
    },
    {
      snapshot_time: "20:00",
      bookmaker: "pinnacle",
      market_line: "0.00",
      home_odds: "1.900",
      draw_odds: "3.500",
      away_odds: "3.900"
    }
  ]
};

export const mockTeamDisplayNameWorkspaces: TeamDisplayNameWorkspace[] = [
  {
    league_id: 39,
    league_name: "Premier League",
    league_display_name: "英超",
    season: 2025,
    is_translation_done: false,
    teams: [
      {
        league_id: 39,
        league_name: "Premier League",
        league_display_name: "英超",
        season: 2025,
        team_id: 33,
        team_name: "Manchester United",
        team_display_name: "曼联",
        team_logo_url: "https://media.api-sports.io/football/teams/33.png",
        is_missing_display_name: false,
        match_count: 38,
        latest_kickoff_time: "2026-05-17T22:00:00+08:00",
        rank: 5,
        points: 67
      },
      {
        league_id: 39,
        league_name: "Premier League",
        league_display_name: "英超",
        season: 2025,
        team_id: 66,
        team_name: "Wolves",
        team_display_name: null,
        team_logo_url: "https://media.api-sports.io/football/teams/39.png",
        is_missing_display_name: true,
        match_count: 38,
        latest_kickoff_time: "2026-05-17T22:00:00+08:00",
        rank: 14,
        points: 41
      },
      {
        league_id: 39,
        league_name: "Premier League",
        league_display_name: "英超",
        season: 2025,
        team_id: 63,
        team_name: "Leeds",
        team_display_name: "利兹联",
        team_logo_url: "https://media.api-sports.io/football/teams/63.png",
        is_missing_display_name: false,
        match_count: 38,
        latest_kickoff_time: "2026-05-17T22:00:00+08:00",
        rank: 17,
        points: 35
      },
      {
        league_id: 39,
        league_name: "Premier League",
        league_display_name: "英超",
        season: 2025,
        team_id: 55,
        team_name: "Brentford",
        team_display_name: null,
        team_logo_url: "https://media.api-sports.io/football/teams/55.png",
        is_missing_display_name: true,
        match_count: 38,
        latest_kickoff_time: "2026-05-17T22:00:00+08:00",
        rank: 11,
        points: 48
      }
    ]
  },
  {
    league_id: 78,
    league_name: "Bundesliga",
    league_display_name: "德甲",
    season: 2025,
    is_translation_done: true,
    teams: [
      {
        league_id: 78,
        league_name: "Bundesliga",
        league_display_name: "德甲",
        season: 2025,
        team_id: 157,
        team_name: "Bayern Munich",
        team_display_name: "拜仁慕尼黑",
        team_logo_url: "https://media.api-sports.io/football/teams/157.png",
        is_missing_display_name: false,
        match_count: 34,
        latest_kickoff_time: "2026-05-16T21:30:00+08:00",
        rank: 1,
        points: 78
      },
      {
        league_id: 78,
        league_name: "Bundesliga",
        league_display_name: "德甲",
        season: 2025,
        team_id: 165,
        team_name: "Borussia Dortmund",
        team_display_name: "多特蒙德",
        team_logo_url: "https://media.api-sports.io/football/teams/165.png",
        is_missing_display_name: false,
        match_count: 34,
        latest_kickoff_time: "2026-05-16T21:30:00+08:00",
        rank: 3,
        points: 64
      }
    ]
  },
  {
    league_id: 40,
    league_name: "Championship",
    league_display_name: "英冠",
    season: 2025,
    is_translation_done: false,
    teams: [
      {
        league_id: 40,
        league_name: "Championship",
        league_display_name: "英冠",
        season: 2025,
        team_id: 72,
        team_name: "Cardiff",
        team_display_name: "卡迪夫城",
        team_logo_url: "https://media.api-sports.io/football/teams/72.png",
        is_missing_display_name: false,
        match_count: 46,
        latest_kickoff_time: "2026-05-03T22:00:00+08:00",
        rank: 9,
        points: 65
      },
      {
        league_id: 40,
        league_name: "Championship",
        league_display_name: "英冠",
        season: 2025,
        team_id: 76,
        team_name: "Swansea",
        team_display_name: null,
        team_logo_url: "https://media.api-sports.io/football/teams/76.png",
        is_missing_display_name: true,
        match_count: 46,
        latest_kickoff_time: "2026-05-03T22:00:00+08:00",
        rank: 12,
        points: 58
      }
    ]
  }
];

export const mockTrainingWorkspace: TrainingWorkspace = {
  dataset: {
    exists: true,
    path: "local_data/training/baseline_main_leagues_20260529.csv",
    updated_at: "2026-05-29T18:10:00",
    size_bytes: 1441170,
    row_count: 5330,
    column_count: 42
  },
  dataset_report: {
    exists: true,
    path: "docs/数据审计/20260529-baseline-training-dataset.md",
    updated_at: "2026-05-29T18:10:00",
    size_bytes: 1200
  },
  qa: {
    exists: true,
    path: "docs/数据审计/20260529-baseline-training-dataset-qa.md",
    updated_at: "2026-05-29T18:20:00",
    empty_required_cells: 0,
    invalid_odds_cells: 0,
    invalid_probability_cells: 0,
    invalid_overround_cells: 0,
    thin_history_count: 152,
    thin_history_ratio: "0.0285",
    low_sample_leagues: { "Ykkosliiga (Finland)": 29 }
  },
  market_baseline: {
    exists: true,
    path: "docs/模型实验/20260529-close-market-baseline-evaluation.md",
    updated_at: "2026-05-29T18:30:00",
    market_samples: 15990,
    evaluated_market_samples: 15326,
    skipped_market_samples: 664,
    market_reports: {
      asian_handicap: {
        evaluated_count: 4928,
        skipped_count: 402,
        accuracy: "0.5244",
        log_loss: "0.6921",
        brier: "0.4412",
        overround: "1.0273",
        flat_bet_profit_units: "-92.6695",
        flat_bet_roi: "-0.0188",
        predicted_side_counts: { home: 2527, away: 2401 }
      },
      total_goals: {
        evaluated_count: 5068,
        skipped_count: 262,
        accuracy: "0.5199",
        log_loss: "0.6924",
        brier: "0.4474",
        overround: "1.0320",
        flat_bet_profit_units: "-111.2930",
        flat_bet_roi: "-0.0220",
        predicted_side_counts: { over: 2560, under: 2508 }
      },
      match_winner: {
        evaluated_count: 5330,
        skipped_count: 0,
        accuracy: "0.5032",
        log_loss: "1.0055",
        brier: "0.6015",
        overround: "1.0390",
        flat_bet_profit_units: "-190.4020",
        flat_bet_roi: "-0.0357",
        predicted_side_counts: { home: 3608, away: 1690, draw: 32 }
      }
    }
  },
  latest_run: {
    id: 3,
    run_type: "full_refresh",
    status: "success",
    started_at: "2026-05-30T13:23:00+08:00",
    finished_at: "2026-05-30T13:28:00+08:00",
    snapshot_tag: "20260530-1323",
    current_step: "finalize",
    error_step: null,
    error_message: null,
    dataset_rows: 5330,
    eligible_matches: 5981,
    complete_matches: 5330,
    coverage_ratio: "0.8912",
    last_trained_match_id: 177,
    last_trained_match_summary: "日职联 神户胜利船 1-0 鹿岛鹿角",
    last_trained_kickoff_time: "2026-05-30T18:00:00+08:00",
    new_complete_matches: null,
    artifact_paths: {
      away_cover_stability_report_path:
        "docs/模型实验/20260530-1323-baseline-away-cover-stability-v1.md",
      dataset_path: "local_data/training/baseline_main_leagues_20260530-1323.csv",
      dynamic_feature_path:
        "local_data/training/baseline_dynamic_features_main_leagues_20260530-1323.csv"
    }
  }
};

export const mockPaperRecommendationWorkspace: PaperRecommendationWorkspace = {
  strategies: [
    {
      strategy_key: "asian_away_cover_hgb_edge_v1",
      display_name: "亚盘客队方向 · HGB边际 v1",
      market_type: "asian_handicap",
      side: "away_cover",
      edge_threshold: "0.1000",
      model_name: "raw_hgb_team_form_plus_all_markets",
      signal_version: "v1"
    }
  ],
  candidates: [
    {
      match_id: 17446,
      source_match_id: "17446",
      kickoff_time: "2026-05-30T02:45:00+08:00",
      league_name: "Premier Division",
      league_display_name: "爱超",
      home_team_name: "Drogheda United",
      home_team_display_name: "德罗赫达联",
      away_team_name: "Waterford",
      away_team_display_name: "沃特福德联",
      status: "candidate",
      market_type: "asian_handicap",
      side: "away_cover",
      recommended_handicap: "客队 +0.50",
      line: "-0.50",
      odds: "1.930",
      model_probability: "0.6500",
      market_probability: "0.5000",
      edge: "0.1500",
      scoring_edge: "0.1200",
      line_bucket: "away_underdog",
      risk_tags: ["line_bucket:away_underdog"],
      strategy_key: "asian_away_cover_hgb_edge_v1",
      strategy_display_name: "亚盘客队方向 · HGB边际 v1",
      signal_version: "v1",
      odds_source: "oddspapi_historical",
      execution_target: "T-10",
      historical_snapshot_count: 42,
      robustness_mode: "filter",
      robustness_status: "kept",
      robustness_primary_target: 10,
      robustness_seen_count: 6,
      robustness_min_edge: "0.1200",
      robustness_observed_targets: [10, 15, 20, 25, 30, 60],
      is_recordable: true
    }
  ],
  records: [
    {
      id: 1,
      match_id: 17446,
      source_match_id: "17446",
      created_at: "2026-05-30T01:00:00+08:00",
      updated_at: "2026-05-30T01:10:00+08:00",
      kickoff_time: "2026-05-30T02:45:00+08:00",
      league_name: "Premier Division",
      league_display_name: "爱超",
      home_team_name: "Drogheda United",
      home_team_display_name: "德罗赫达联",
      away_team_name: "Waterford",
      away_team_display_name: "沃特福德联",
      strategy_key: "asian_away_cover_hgb_edge_v1",
      strategy_display_name: "亚盘客队方向 · HGB边际 v1",
      model_name: "raw_hgb_team_form_plus_all_markets",
      signal_version: "v1",
      market_type: "asian_handicap",
      side: "away_cover",
      recommended_handicap: "客队 +0.25",
      original_recommended_handicap: "客队 +0.50",
      line_bucket: "away_underdog",
      risk_tags: ["line_bucket:away_underdog"],
      original_market_line: "-0.50",
      original_odds: "1.930",
      current_market_line: "-0.25",
      current_odds: "1.880",
      model_probability: "0.6500",
      market_probability: "0.5000",
      edge: "0.1500",
      scoring_edge: "0.1200",
      stake_units: "1.00",
      status: "settled",
      is_manually_adjusted: true,
      manual_note: "临场退盘",
      settlement_result: "half_win",
      profit_units: "0.440",
      settled_at: "2026-05-30T05:00:00+08:00"
    }
  ],
  summary: {
    total_records: 1,
    pending_records: 0,
    settled_records: 1,
    void_records: 0,
    candidate_count: 1,
    total_stake_units: "1.00",
    total_profit_units: "0.440",
    hit_rate: "1.0000",
    roi: "0.4400"
  },
  groups: {
    by_strategy: [
      {
        group_name: "亚盘客队方向 · HGB边际 v1",
        record_count: 1,
        settled_records: 1,
        total_stake_units: "1.00",
        total_profit_units: "0.440",
        hit_rate: "1.0000",
        roi: "0.4400"
      }
    ],
    by_league: [
      {
        group_name: "爱超",
        record_count: 1,
        settled_records: 1,
        total_stake_units: "1.00",
        total_profit_units: "0.440",
        hit_rate: "1.0000",
        roi: "0.4400"
      }
    ],
    by_line_bucket: [
      {
        group_name: "away_underdog",
        record_count: 1,
        settled_records: 1,
        total_stake_units: "1.00",
        total_profit_units: "0.440",
        hit_rate: "1.0000",
        roi: "0.4400"
      }
    ],
    by_manual_adjustment: [
      {
        group_name: "人工调整",
        record_count: 1,
        settled_records: 1,
        total_stake_units: "1.00",
        total_profit_units: "0.440",
        hit_rate: "1.0000",
        roi: "0.4400"
      }
    ]
  }
};

export const mockMatchListWorkspace: MatchListWorkspace = {
  filters: {
    start_time: "2026-05-30T00:00:00+08:00",
    end_time: "2026-05-31T12:00:00+08:00",
    league_name: null,
    status_filter: "all",
    odds_filter: "all",
    search: null
  },
  freshness: {
    latest_fixtures_results_sync: "2026-05-30T10:12:00+08:00",
    latest_odds_sync: "2026-05-30T10:16:00+08:00",
    latest_kickoff_time: "2026-06-02T03:00:00+08:00",
    latest_odds_snapshot_time: "2026-05-30T10:15:00+08:00"
  },
  leagues: [
    { name: "J1 League", display_name: "日职联" },
    { name: "K League 1", display_name: "韩K联" }
  ],
  total_matches: 2,
  matches: [
    {
      match_id: 16356,
      kickoff_time: "2026-05-30T13:00:00+08:00",
      league_name: "J1 League",
      league_display_name: "日职联",
      home_team_name: "Sanfrecce Hiroshima",
      home_team_display_name: "广岛三箭",
      home_team_logo_url: "home.png",
      away_team_name: "Kawasaki Frontale",
      away_team_display_name: "川崎前锋",
      away_team_logo_url: "away.png",
      status: "scheduled",
      status_group: "not_started",
      home_score: null,
      away_score: null,
      has_odds: true,
      odds_status_key: "close",
      odds_status_label: "临盘",
      odds_summary: {
        asian_handicap: "客队 +0.50 @ 1.950",
        total_goals: null,
        match_winner: null
      }
    },
    {
      match_id: 16357,
      kickoff_time: "2026-05-30T13:00:00+08:00",
      league_name: "J1 League",
      league_display_name: "日职联",
      home_team_name: "Nagoya Grampus",
      home_team_display_name: "名古屋鲸鱼",
      home_team_logo_url: null,
      away_team_name: "Machida Zelvia",
      away_team_display_name: "町田泽维亚",
      away_team_logo_url: null,
      status: "scheduled",
      status_group: "not_started",
      home_score: null,
      away_score: null,
      has_odds: false,
      odds_status_key: "none",
      odds_status_label: "无赔率",
      odds_summary: {
        asian_handicap: null,
        total_goals: null,
        match_winner: null
      }
    }
  ]
};

export const mockMatchDetail: MatchDetail = {
  ...mockMatchListWorkspace.matches[0],
  team_data_note: "待接入",
  execution_timepoint_coverage: {
    targets: ["T-60", "T-30", "T-25", "T-20", "T-15", "T-10"],
    available_count: 0,
    total_count: 18,
    health_key: "none",
    health_label: "无覆盖",
    rows: [
      {
        market_type: "asian_handicap",
        market_label: "亚盘",
        cells: ["T-60", "T-30", "T-25", "T-20", "T-15", "T-10"].map((label) => ({
          target_minutes: Number(label.slice(2)),
          label,
          available: false,
          snapshot_time: null,
          market_line: null
        }))
      },
      {
        market_type: "total_goals",
        market_label: "大小球",
        cells: ["T-60", "T-30", "T-25", "T-20", "T-15", "T-10"].map((label) => ({
          target_minutes: Number(label.slice(2)),
          label,
          available: false,
          snapshot_time: null,
          market_line: null
        }))
      },
      {
        market_type: "match_winner",
        market_label: "胜平负",
        cells: ["T-60", "T-30", "T-25", "T-20", "T-15", "T-10"].map((label) => ({
          target_minutes: Number(label.slice(2)),
          label,
          available: false,
          snapshot_time: null,
          market_line: null
        }))
      }
    ]
  },
  paper_recommendation_summary: { count: 0, label: "暂无纸面推荐记录" },
  formal_recommendation_summary: { count: 0, label: "暂无正式推荐记录" }
};

export const mockOddspapiBackfillAudit: OddspapiBackfillAudit = {
  season: 2025,
  log_dir: "logs/odds",
  worker_progress: {
    status: "running",
    mode: "balanced",
    season: 2025,
    updated_at: "2026-05-27T10:15:00+08:00",
    current_league_id: "40",
    current_league_name: "Championship",
    current_league_display_name: "英冠",
    round: 12,
    processed_matches: 18,
    inserted_snapshots: 540,
    failed_matches: 2,
    requests_used: 31,
    total_processed_matches: 180,
    total_inserted_snapshots: 5400,
    total_failed_matches: 12,
    total_requests_used: 310
  },
  league_summaries: [
    {
      league_name: "Championship",
      league_display_name: "英冠",
      source_league_id: "40",
      finished_matches: 552,
      matched_matches: 494,
      snapshot_matches: 494,
      snapshot_count: 14820,
      asian_handicap_snapshot_count: 7410,
      total_goals_snapshot_count: 7410,
      status_counts: { success: 494, unmatched: 12, failed: 4 },
      error_counts: { "team-name-mismatch": 8, "fixture-window-empty": 4 }
    },
    {
      league_name: "Premier League",
      league_display_name: "英超",
      source_league_id: "39",
      finished_matches: 380,
      matched_matches: 350,
      snapshot_matches: 350,
      snapshot_count: 10500,
      asian_handicap_snapshot_count: 5250,
      total_goals_snapshot_count: 5250,
      status_counts: { success: 350, unmatched: 8 },
      error_counts: { "same-kickoff-candidate-mismatch": 3 }
    },
    {
      league_name: "Bundesliga",
      league_display_name: "德甲",
      source_league_id: "78",
      finished_matches: 306,
      matched_matches: 286,
      snapshot_matches: 286,
      snapshot_count: 8580,
      asian_handicap_snapshot_count: 4290,
      total_goals_snapshot_count: 4290,
      status_counts: { success: 286, empty: 6 },
      error_counts: {}
    }
  ]
};

export const mockDashboardData: DashboardData = {
  source: "mock",
  summary: {
    total_matches: 13112,
    finished_matches: 12980,
    matches_with_historical_odds: 1844,
    historical_odds_snapshots: 183204,
    unmatched_matches: 217
  },
  leagues: [
    {
      league_id: 39,
      league_name: "Premier League",
      league_display_name: "英超",
      country_or_region: "England",
      season: 2025,
      finished_matches: 380,
      matches_with_historical_odds: 350,
      coverage_ratio: "0.9211",
      unmatched_matches: 8
    },
    {
      league_id: 78,
      league_name: "Bundesliga",
      league_display_name: "德甲",
      country_or_region: "Germany",
      season: 2025,
      finished_matches: 306,
      matches_with_historical_odds: 286,
      coverage_ratio: "0.9346",
      unmatched_matches: 4
    },
    {
      league_id: 40,
      league_name: "Championship",
      league_display_name: "英冠",
      country_or_region: "England",
      season: 2025,
      finished_matches: 552,
      matches_with_historical_odds: 494,
      coverage_ratio: "0.8949",
      unmatched_matches: 12
    },
    {
      league_id: 283,
      league_name: "Liga I",
      league_display_name: "罗甲",
      country_or_region: "Romania",
      season: 2025,
      finished_matches: 240,
      matches_with_historical_odds: 18,
      coverage_ratio: "0.0750",
      unmatched_matches: 33
    }
  ],
  workers: [
    {
      pid: 27776,
      status: "running",
      runtime_status: "running",
      mode: "balanced",
      season: 2025,
      league_ids: ["106", "114", "119", "128", "203", "235", "265", "283"],
      process_log_path: "logs/odds/20260525-210422-oddspapi-worker-process.log",
      notify_on_complete: true
    }
  ],
  oddspapiBackfillAudit: mockOddspapiBackfillAudit,
  unmatched: [
    {
      match_id: 1002,
      league_name: "英超",
      home_team_name: "Wolves",
      away_team_name: "Leeds",
      kickoff_time: "2026-05-21T22:00:00+08:00",
      match_reason: "未匹配到 OddsPapi 比赛",
      alias_candidates: ["Wolverhampton Wanderers", "Wolverhampton", "Wolves FC"]
    },
    {
      match_id: 1308,
      league_name: "土超",
      home_team_name: "Istanbul Basaksehir",
      away_team_name: "Rizespor",
      kickoff_time: "2026-05-18T01:00:00+08:00",
      match_reason: "队名相似度低于阈值",
      alias_candidates: ["Başakşehir", "Istanbul BB", "Basaksehir FK"]
    }
  ],
  oddsTrends: mockOddsTrends,
  matchesWithOdds: [
    {
      match_id: 1001,
      league_name: "英冠",
      home_team_name: "Cardiff",
      away_team_name: "Swansea",
      kickoff_time: "2026-05-20T22:00:00+08:00",
      snapshot_count: 6
    }
  ],
  missingTeamDisplayNames: [
    ...mockTeamDisplayNameWorkspaces.flatMap((workspace) =>
      workspace.teams.filter((team) => team.is_missing_display_name)
    )
  ],
  doneDisplayTranslationKeys: ["78-2025"],
  trainingWorkspace: mockTrainingWorkspace,
  paperRecommendations: mockPaperRecommendationWorkspace,
  matchList: mockMatchListWorkspace,
  recommendationRecords: []
};
