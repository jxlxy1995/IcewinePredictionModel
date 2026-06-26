import { describe, expect, it, vi } from "vitest";

import {
  dashboardNavItems,
  refreshMatchDetailWithOddsTrend,
  initialDashboardView,
  shouldAutoLoadLazyView
} from "./pages/DashboardPage";
import { mockDashboardData, mockMatchDetail } from "./mockData";
import type { MatchDetail, MatchOddsTrends } from "./types";

describe("dashboard navigation", () => {
  it("keeps only active workflow pages in the sidebar", () => {
    expect(dashboardNavItems.map((item) => item.key)).toEqual([
      "matchList",
      "automationTasks",
      "displayNames",
      "models",
      "paperTracking",
      "paperSnapshotReview",
      "records"
    ]);
  });

  it("opens the match list by default", () => {
    expect(initialDashboardView).toBe("matchList");
  });

  it("does not show mocked recommendation records", () => {
    expect(mockDashboardData.recommendationRecords).toEqual([]);
  });

  it("loads review pages that should show persisted data on first open", () => {
    expect(shouldAutoLoadLazyView("paperTracking")).toBe(false);
    expect(shouldAutoLoadLazyView("paperSnapshotReview")).toBe(true);
    expect(shouldAutoLoadLazyView("automationTasks")).toBe(true);
    expect(shouldAutoLoadLazyView("matchList")).toBe(true);
    expect(shouldAutoLoadLazyView("models")).toBe(true);
  });

  it("refreshes both match detail and odds trend after odds data changes", async () => {
    const detail: MatchDetail = {
      ...mockMatchDetail,
      has_odds: true,
      odds_status_key: "basic",
      odds_status_label: "Basic"
    };
    const trends: MatchOddsTrends = {
      match_id: detail.match_id,
      league_name: detail.league_name,
      home_team_name: detail.home_team_name,
      away_team_name: detail.away_team_name,
      kickoff_time: detail.kickoff_time,
      asian_handicap: [{ snapshot_time: "2026-05-30T12:40:00+08:00", bookmaker: "pinnacle", market_line: "-0.50", home_odds: "1.900", away_odds: "1.960" }],
      total_goals: [],
      match_winner: []
    };
    const setDetail = vi.fn();
    const setTrends = vi.fn();
    const setTrendError = vi.fn();

    await refreshMatchDetailWithOddsTrend({
      matchId: detail.match_id,
      loadDetail: async () => detail,
      loadOddsTrend: async () => trends,
      setDetail,
      setOddsTrends: setTrends,
      setOddsError: setTrendError
    });

    expect(setDetail).toHaveBeenCalledWith(detail);
    expect(setTrends).toHaveBeenCalledWith(trends);
    expect(setTrendError).toHaveBeenCalledWith(null);
  });
});
