import { describe, expect, it } from "vitest";

import {
  buildPaperCandidateGroups,
  buildPaperCandidateRows,
  buildPaperConfidenceSimulationCards,
  buildPaperConfidenceSimulationRows,
  buildPaperDiagnosticCards,
  buildPaperRecordGroups,
  buildPaperSummaryCards,
  defaultPaperRecommendationDateRange,
  explainPaperCandidateSignal,
  formatPaperRecordStatus,
  formatPaperSettlementResult
} from "./paperRecommendationWorkspace";
import type { PaperRecommendationWorkspace } from "./types";

const workspace: PaperRecommendationWorkspace = {
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
    by_strategy: [],
    by_league: [],
    by_line_bucket: [],
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
  },
  confidence_simulation: {
    summary: {
      group_count: 1,
      settled_groups: 1,
      suggested_stake_units: "1.25",
      flat_profit_units: "0.930",
      weighted_profit_units: "1.163",
      flat_roi: "0.9300",
      weighted_roi: "0.9304"
    },
    groups: [
      {
        group_key: "17446:asian_handicap:away_cover",
        match_id: 17446,
        source_match_id: "17446",
        kickoff_time: "2026-05-30T02:45:00+08:00",
        league_name: "Premier Division",
        league_display_name: "League Display",
        home_team_name: "Drogheda United",
        home_team_display_name: "Drogheda",
        home_team_logo_url: "https://img.example/home.png",
        home_score: 1,
        away_team_name: "Waterford",
        away_team_display_name: "Waterford",
        away_team_logo_url: "https://img.example/away.png",
        away_score: 1,
        market_type: "asian_handicap",
        logical_side: "away_cover",
        recommendation_text: "Away +0.50",
        representative_record_id: 1,
        representative_strategy_key: "asian_away_cover_hgb_bucket_v2",
        representative_market_line: "-0.50",
        representative_odds: "1.930",
        signal_record_ids: [1],
        triggered_strategy_keys: [
          "asian_away_cover_hgb_edge_v1",
          "asian_away_cover_hgb_bucket_v2"
        ],
        triggered_strategy_display_names: [
          "Asian away HGB edge v1",
          "Asian away HGB bucket v2"
        ],
        signal_families: ["asian_away_hgb"],
        confidence_score: 72,
        suggested_stake_units: "1.25",
        stake_cap_reason: "same_family_cap",
        status: "settled",
        settlement_result: "win",
        flat_profit_units: "0.930",
        weighted_profit_units: "1.163",
        warning: null
      }
    ],
    by_score_bucket: [],
    by_stake_bucket: [],
    by_family_combo: []
  },
  diagnostics: {
    total_matches: 3,
    candidate_count: 1,
    candidate_match_count: 1,
    edge_threshold: "0.1000",
    discarded_by_robustness_match_count: 0,
    status_counts: {
      below_threshold: 1,
      candidate: 1,
      odds_status_not_ready: 1
    }
  }
};

describe("paperRecommendationWorkspace", () => {
  it("builds summary cards with percentage formatting", () => {
    expect(buildPaperSummaryCards(workspace)).toEqual([
      { label: "候选信号", value: "1" },
      { label: "已记录信号", value: "1" },
      { label: "待结算信号", value: "0" },
      { label: "信号命中率", value: "100.00%" },
      { label: "信号ROI", value: "44.00%" }
    ]);
  });

  it("defaults paper filters to yesterday midnight through today midnight", () => {
    const range = defaultPaperRecommendationDateRange(new Date(2026, 5, 2, 15, 24));

    expect(range).toEqual({
      start_time: "2026-06-01T00:00",
      end_time: "2026-06-02T00:00"
    });
  });

  it("builds paper diagnostic cards from queue status counts", () => {
    expect(buildPaperDiagnosticCards(workspace)).toEqual([
      { label: "扫描比赛", value: "3", meta: "候选窗口内" },
      { label: "候选比赛", value: "1", meta: "唯一比赛" },
      { label: "候选信号", value: "1", meta: "可记录信号" },
      { label: "赔率不合格", value: "1", meta: "无赔率/未就绪/过期" },
      { label: "未过阈值", value: "1", meta: "edge < 0.1000" },
      { label: "未出分", value: "0", meta: "模型无结果" }
    ]);
  });

  it("explains a paper candidate signal with probabilities and edge formula", () => {
    expect(explainPaperCandidateSignal(workspace.candidates[0])).toEqual({
      title: "亚盘客队方向 · HGB边际 v1",
      formula: "edge = 模型概率 0.6500 - 市场概率 0.5000 = 0.1500",
      verdict: "高于阈值 0.1000，进入纸面候选。",
      facts: [
        "盘口/选择：客队 +0.50 @ 1.930",
        "市场类型：亚盘",
        "风险标签：line_bucket:away_underdog"
      ]
    });
  });

  it("marks only candidate rows as recordable", () => {
    expect(buildPaperCandidateRows(workspace)[0]).toMatchObject({
      fixture: "德罗赫达联 vs 沃特福德联",
      isRecordable: true,
      recommendation: "客队 +0.50 @ 1.930",
      strategyLabel: "亚盘客队方向 · HGB边际 v1"
    });
  });

  it("groups candidate signals by match and promotes the strongest recordable signal", () => {
    const groupedWorkspace: PaperRecommendationWorkspace = {
      ...workspace,
      candidates: [
        {
          ...workspace.candidates[0],
          strategy_key: "asian_away_cover_hgb_edge_v1",
          strategy_display_name: "亚盘客队方向 · HGB边际 v1",
          market_type: "asian_handicap",
          side: "away_cover",
          edge: "0.1500",
          recommended_handicap: "客队 +0.50"
        },
        {
          ...workspace.candidates[0],
          strategy_key: "total_over_edge_v1",
          strategy_display_name: "大小球大球 · Edge v1",
          market_type: "total_goals",
          side: "over",
          edge: "0.2200",
          recommended_handicap: "大 2.50"
        },
        {
          ...workspace.candidates[0],
          strategy_key: "home_win_edge_v1",
          strategy_display_name: "胜平负主胜 · Edge v1",
          market_type: "match_winner",
          side: "home",
          status: "already_recorded",
          edge: "0.3000",
          recommended_handicap: "主胜",
          is_recordable: false
        },
        {
          ...workspace.candidates[0],
          match_id: 17447,
          source_match_id: "17447",
          home_team_name: "Galway United",
          home_team_display_name: "戈尔韦联",
          away_team_name: "Shamrock Rovers",
          away_team_display_name: "沙姆洛克流浪",
          edge: "0.1200"
        }
      ],
      summary: { ...workspace.summary, candidate_count: 3 }
    };

    const groups = buildPaperCandidateGroups(groupedWorkspace);

    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({
      fixture: "德罗赫达联 vs 沃特福德联",
      signalCount: 3,
      recordableCount: 2,
      main: {
        edge: "0.2200",
        recommendation: "大 2.50 @ 1.930",
        strategyLabel: "大小球大球 · Edge v1"
      }
    });
    expect(groups[0].recordableSignals.map((signal) => signal.signalKey)).toEqual([
      "17446:asian_away_cover_hgb_edge_v1:asian_handicap:away_cover",
      "17446:total_over_edge_v1:total_goals:over"
    ]);
    expect(groups[0].signals.map((signal) => signal.signalKey)).toEqual([
      "17446:asian_away_cover_hgb_edge_v1:asian_handicap:away_cover",
      "17446:total_over_edge_v1:total_goals:over",
      "17446:home_win_edge_v1:match_winner:home"
    ]);
  });

  it("passes through grouped summaries for review tables", () => {
    expect(buildPaperRecordGroups(workspace).byManualAdjustment[0]).toMatchObject({
      groupName: "人工调整",
      roi: "44.00%"
    });
  });

  it("builds confidence simulation cards with weighted ROI", () => {
    expect(buildPaperConfidenceSimulationCards(workspace)).toEqual([
      { label: "推荐组", value: "1" },
      { label: "已结算", value: "1" },
      { label: "建议手数", value: "1.25" },
      { label: "1手ROI", value: "93.00%" },
      { label: "动态ROI", value: "93.04%" }
    ]);
  });

  it("builds confidence simulation rows for display", () => {
    expect(buildPaperConfidenceSimulationRows(workspace)[0]).toMatchObject({
      confidenceScore: "72",
      fixture: "Drogheda vs Waterford",
      home_team_logo_url: "https://img.example/home.png",
      homeScore: 1,
      id: 1,
      kickoff_time: "2026-05-30T02:45:00+08:00",
      recommendation: "Away +0.50 @ 1.930",
      signalRecordIds: [1],
      suggestedStakeUnits: "1.25",
      triggeredSignals: "asian_away_cover_hgb_edge_v1, asian_away_cover_hgb_bucket_v2",
      weightedProfitUnits: "1.163"
    });
  });

  it("formats statuses and settlement results", () => {
    expect(formatPaperRecordStatus("pending")).toBe("待结算");
    expect(formatPaperRecordStatus("void")).toBe("已作废");
    expect(formatPaperSettlementResult("half_win")).toBe("赢半");
    expect(formatPaperSettlementResult(null)).toBe("-");
  });
});
