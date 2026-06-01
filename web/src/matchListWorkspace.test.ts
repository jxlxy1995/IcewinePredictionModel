import { describe, expect, it } from "vitest";

import {
  buildMatchFreshnessCards,
  buildMatchListRows,
  buildMatchSyncSummary,
  defaultMatchListDateRange,
  formatMatchStatus,
  formatOddsAvailability,
  summarizeMatchDetail
} from "./matchListWorkspace";
import type { MatchDetail, MatchListWorkspace } from "./types";

const workspace: MatchListWorkspace = {
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
  leagues: [{ name: "J1 League", display_name: "J1" }],
  total_matches: 1,
  matches: [
    {
      match_id: 16356,
      kickoff_time: "2026-05-30T13:00:00+08:00",
      league_name: "J1 League",
      league_display_name: "J1",
      home_team_name: "Sanfrecce Hiroshima",
      home_team_display_name: "Hiroshima",
      home_team_logo_url: "home.png",
      away_team_name: "Kawasaki Frontale",
      away_team_display_name: "Kawasaki",
      away_team_logo_url: "away.png",
      status: "scheduled",
      status_group: "not_started",
      home_score: null,
      away_score: null,
      has_odds: true,
      odds_status_key: "close",
      odds_status_label: "临盘",
      odds_summary: {
        asian_handicap: "Away +0.50 @ 1.950",
        total_goals: null,
        match_winner: null
      }
    }
  ]
};

const detail: MatchDetail = {
  ...workspace.matches[0],
  team_data_note: "Pending",
  paper_recommendation_summary: { count: 0, label: "No paper records" },
  formal_recommendation_summary: { count: 0, label: "No formal records" }
};

describe("matchListWorkspace", () => {
  it("builds compact freshness cards", () => {
    expect(buildMatchFreshnessCards(workspace).map((card) => card.value)).toEqual([
      "2026-05-30 10:12",
      "2026-05-30 10:16",
      "2026-06-02 03:00",
      "2026-05-30 10:15"
    ]);
  });

  it("formats match list rows with display names", () => {
    expect(buildMatchListRows(workspace)[0]).toMatchObject({
      fixture: "Hiroshima vs Kawasaki",
      league: "J1",
      oddsAvailability: "临盘"
    });
  });

  it("formats default datetime-local range from today to tomorrow noon", () => {
    const range = defaultMatchListDateRange(new Date(2026, 4, 30, 15, 24));

    expect(range).toEqual({
      start_time: "2026-05-30T00:00",
      end_time: "2026-05-31T12:00"
    });
  });

  it("formats status text and odds availability", () => {
    expect(formatMatchStatus("scheduled")).toBe("未开赛");
    expect(formatMatchStatus("pending_result")).toBe("待填赛果");
    expect(formatMatchStatus("1h")).toBe("待填赛果");
    expect(formatMatchStatus("2H")).toBe("待填赛果");
    expect(formatMatchStatus("ht")).toBe("待填赛果");
    expect(formatMatchStatus("custom_status")).toBe("custom_status");
    expect(formatOddsAvailability(true)).not.toBe("-");
  });

  it("summarizes match detail placeholders", () => {
    expect(summarizeMatchDetail(detail)).toEqual({
      fixture: "Hiroshima vs Kawasaki",
      recommendations: "No paper records / No formal records",
      teamData: "Pending"
    });
  });

  it("builds match sync summary labels", () => {
    expect(
      buildMatchSyncSummary({
        sync_type: "odds",
        started_at: "2026-05-30T10:00:00+08:00",
        finished_at: "2026-05-30T10:01:00+08:00",
        target_count: 4,
        success_count: 2,
        failed_count: 1,
        skipped_count: 1,
        requests_used: 8,
        success: [],
        failed: [],
        skipped: []
      })
    ).toEqual({
      title: "赔率同步结果",
      line: "目标 4 场，成功 2，失败 1，跳过 1，请求 8"
    });
  });
});
