import type {
  DashboardData,
  MatchOddsTrends,
  ModelTrainingOverview,
  TeamDisplayNameWorkspace
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

export const mockModelTrainingOverview: ModelTrainingOverview = {
  generated_at: "2026-05-26T11:45:00+08:00",
  total_training_matches: 1844,
  total_training_snapshots: 183204,
  model_runs: [
    {
      model_name: "Dixon-Coles 攻防强度",
      model_version: "dixon-coles-attack-defense-v1",
      status: "ready",
      trained_at: "2026-05-25T18:12:00+08:00",
      sample_count: 1844,
      league_count: 42,
      market_types: ["score_distribution", "asian_handicap", "total_goals"],
      validation_log_loss: "0.6541",
      validation_brier_score: "0.1988"
    },
    {
      model_name: "Skellam 净胜球",
      model_version: "skellam-margin-v1",
      status: "ready",
      trained_at: "2026-05-25T20:36:00+08:00",
      sample_count: 1420,
      league_count: 35,
      market_types: ["asian_handicap"],
      validation_log_loss: "0.6812",
      validation_brier_score: "0.2134"
    },
    {
      model_name: "负二项总进球",
      model_version: "negative-binomial-total-v1",
      status: "training",
      trained_at: "2026-05-26T10:30:00+08:00",
      sample_count: 1320,
      league_count: 31,
      market_types: ["total_goals"],
      validation_log_loss: null,
      validation_brier_score: null
    }
  ],
  league_training_coverage: [
    {
      league_name: "Premier League",
      league_display_name: "英超",
      season: 2025,
      finished_matches: 380,
      training_matches: 350,
      coverage_ratio: "0.9211"
    },
    {
      league_name: "Bundesliga",
      league_display_name: "德甲",
      season: 2025,
      finished_matches: 306,
      training_matches: 286,
      coverage_ratio: "0.9346"
    },
    {
      league_name: "Championship",
      league_display_name: "英冠",
      season: 2025,
      finished_matches: 552,
      training_matches: 494,
      coverage_ratio: "0.8949"
    },
    {
      league_name: "Liga I",
      league_display_name: "罗甲",
      season: 2025,
      finished_matches: 240,
      training_matches: 18,
      coverage_ratio: "0.0750"
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
  modelTraining: mockModelTrainingOverview,
  recommendationRecords: [
    {
      id: 1,
      match_id: 1001,
      league_name: "英冠",
      league_display_name: "英冠",
      home_team_name: "Cardiff",
      home_team_display_name: "卡迪夫城",
      away_team_name: "Swansea",
      away_team_display_name: "斯旺西",
      kickoff_time: "2026-05-20T22:00:00+08:00",
      market_type: "asian_handicap",
      side: "home",
      market_line: "-0.25",
      odds: "1.930",
      confidence_grade: "A-",
      stake_units: "1.50",
      status: "settled",
      settlement_result: "win",
      profit_units: "1.395"
    },
    {
      id: 2,
      match_id: 1003,
      league_name: "意甲",
      league_display_name: "意甲",
      home_team_name: "Roma",
      home_team_display_name: "罗马",
      away_team_name: "Lazio",
      away_team_display_name: "拉齐奥",
      kickoff_time: "2026-05-24T02:45:00+08:00",
      market_type: "total_goals",
      side: "over",
      market_line: "2.75",
      odds: "1.910",
      confidence_grade: "B+",
      stake_units: "1.00",
      status: "settled",
      settlement_result: "half_loss",
      profit_units: "-0.500"
    },
    {
      id: 3,
      match_id: 1004,
      league_name: "Premier League",
      league_display_name: "英超",
      home_team_name: "Arsenal",
      home_team_display_name: "阿森纳",
      away_team_name: "Chelsea",
      away_team_display_name: "切尔西",
      kickoff_time: "2026-05-18T23:30:00+08:00",
      market_type: "asian_handicap",
      side: "home",
      market_line: "-0.50",
      odds: "1.880",
      confidence_grade: "A",
      stake_units: "2.00",
      status: "settled",
      settlement_result: "loss",
      profit_units: "-2.000"
    },
    {
      id: 4,
      match_id: 1005,
      league_name: "Bundesliga",
      league_display_name: "德甲",
      home_team_name: "Bayern Munich",
      home_team_display_name: "拜仁慕尼黑",
      away_team_name: "Borussia Dortmund",
      away_team_display_name: "多特蒙德",
      kickoff_time: "2026-05-16T21:30:00+08:00",
      market_type: "asian_handicap",
      side: "away",
      market_line: "+0.75",
      odds: "1.960",
      confidence_grade: "B+",
      stake_units: "1.25",
      status: "settled",
      settlement_result: "half_win",
      profit_units: "0.600"
    },
    {
      id: 5,
      match_id: 1006,
      league_name: "Premier League",
      league_display_name: "英超",
      home_team_name: "Wolves",
      home_team_display_name: "狼队",
      away_team_name: "Leeds",
      away_team_display_name: "利兹联",
      kickoff_time: "2026-05-27T03:00:00+08:00",
      market_type: "total_goals",
      side: "under",
      market_line: "2.50",
      odds: "1.920",
      confidence_grade: "B",
      stake_units: "1.00",
      status: "pending",
      settlement_result: null,
      profit_units: null
    }
  ]
};
