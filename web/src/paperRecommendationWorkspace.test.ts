import { describe, expect, it } from "vitest";

import {
  buildPaperCandidateGroups,
  buildPaperCandidateRows,
  buildPaperRecordGroups,
  buildPaperSummaryCards,
  defaultPaperRecommendationDateRange,
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
  }
};

describe("paperRecommendationWorkspace", () => {
  it("builds summary cards with percentage formatting", () => {
    expect(buildPaperSummaryCards(workspace)).toEqual([
      { label: "候选", value: "1" },
      { label: "已记录", value: "1" },
      { label: "待结算", value: "0" },
      { label: "命中率", value: "100.00%" },
      { label: "ROI", value: "44.00%" }
    ]);
  });

  it("defaults paper filters to yesterday midnight through today midnight", () => {
    const range = defaultPaperRecommendationDateRange(new Date(2026, 5, 2, 15, 24));

    expect(range).toEqual({
      start_time: "2026-06-01T00:00",
      end_time: "2026-06-02T00:00"
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

  it("formats statuses and settlement results", () => {
    expect(formatPaperRecordStatus("pending")).toBe("待结算");
    expect(formatPaperRecordStatus("void")).toBe("已作废");
    expect(formatPaperSettlementResult("half_win")).toBe("赢半");
    expect(formatPaperSettlementResult(null)).toBe("-");
  });
});
