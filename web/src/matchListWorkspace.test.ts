import { describe, expect, it } from "vitest";

import {
  buildMatchFreshnessCards,
  buildMatchListRows,
  formatMatchStatus,
  formatOddsAvailability,
  matchTimePresetLabel,
  summarizeMatchDetail
} from "./matchListWorkspace";
import type { MatchDetail, MatchListWorkspace } from "./types";

const workspace: MatchListWorkspace = {
  filters: {
    time_preset: "next_24h",
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
  leagues: ["J1 League"],
  total_matches: 1,
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
      odds_summary: {
        asian_handicap: "客队 +0.50 @ 1.950",
        total_goals: null,
        match_winner: null
      }
    }
  ]
};

const detail: MatchDetail = {
  ...workspace.matches[0],
  team_data_note: "待接入",
  paper_recommendation_summary: { count: 0, label: "暂无纸面推荐记录" },
  formal_recommendation_summary: { count: 0, label: "暂无正式推荐记录" }
};

describe("matchListWorkspace", () => {
  it("builds compact freshness cards", () => {
    expect(buildMatchFreshnessCards(workspace)).toEqual([
      { label: "赛程/赛果同步", value: "2026-05-30 10:12", meta: "默认 3 天" },
      { label: "赔率同步", value: "2026-05-30 10:16", meta: "默认 2 天" },
      { label: "库内最新开赛", value: "2026-06-02 03:00", meta: "辅助参考" },
      { label: "最新赔率快照", value: "2026-05-30 10:15", meta: "辅助参考" }
    ]);
  });

  it("formats match list rows with Chinese names and odds summary", () => {
    expect(buildMatchListRows(workspace)[0]).toMatchObject({
      fixture: "广岛三箭 vs 川崎前锋",
      league: "日职联",
      oddsText: "客队 +0.50 @ 1.950",
      statusText: "未开赛"
    });
  });

  it("formats filter labels and status text", () => {
    expect(matchTimePresetLabel("next_24h")).toBe("未来 24h");
    expect(formatMatchStatus("finished")).toBe("已完赛");
    expect(formatOddsAvailability(false)).toBe("无赔率");
  });

  it("summarizes match detail placeholders", () => {
    expect(summarizeMatchDetail(detail)).toEqual({
      fixture: "广岛三箭 vs 川崎前锋",
      recommendations: "暂无纸面推荐记录 / 暂无正式推荐记录",
      teamData: "待接入"
    });
  });
});
