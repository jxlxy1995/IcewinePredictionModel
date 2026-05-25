import type { DashboardData, MatchOddsTrends } from "./types";

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
      league_id: 40,
      league_name: "英冠",
      country_or_region: "England",
      season: 2025,
      finished_matches: 552,
      matches_with_historical_odds: 494,
      coverage_ratio: "0.8949",
      unmatched_matches: 12
    },
    {
      league_id: 78,
      league_name: "德甲",
      country_or_region: "Germany",
      season: 2025,
      finished_matches: 306,
      matches_with_historical_odds: 286,
      coverage_ratio: "0.9346",
      unmatched_matches: 4
    },
    {
      league_id: 283,
      league_name: "罗甲",
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
      match_reason: "未匹配到 OddsPapi 比赛"
    },
    {
      match_id: 1308,
      league_name: "土超",
      home_team_name: "Istanbul Basaksehir",
      away_team_name: "Rizespor",
      kickoff_time: "2026-05-18T01:00:00+08:00",
      match_reason: "队名相似度低于阈值"
    }
  ],
  oddsTrends: mockOddsTrends,
  recommendationRecords: [
    {
      id: 1,
      match_id: 1001,
      league_name: "英冠",
      home_team_name: "Cardiff",
      away_team_name: "Swansea",
      kickoff_time: "2026-05-20T22:00:00+08:00",
      market_type: "asian_handicap",
      side: "home",
      market_line: "-0.25",
      odds: "1.930",
      confidence_grade: "A-",
      stake_units: "1.50",
      status: "pending",
      settlement_result: null,
      profit_units: null
    },
    {
      id: 2,
      match_id: 1003,
      league_name: "意甲",
      home_team_name: "Roma",
      away_team_name: "Lazio",
      kickoff_time: "2026-05-24T02:45:00+08:00",
      market_type: "total_goals",
      side: "over",
      market_line: "2.75",
      odds: "1.910",
      confidence_grade: "B+",
      stake_units: "1.00",
      status: "pending",
      settlement_result: null,
      profit_units: null
    }
  ]
};
