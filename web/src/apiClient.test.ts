import { afterEach, describe, expect, it, vi } from "vitest";

import { loadDashboardData, loadPaperRecommendationWorkspace } from "./apiClient";

const apiPayloads: Record<string, unknown> = {
  "/api/dashboard/summary": {
    finished_matches: 2,
    historical_odds_snapshots: 5,
    matches_with_historical_odds: 1,
    total_matches: 3,
    unmatched_matches: 0
  },
  "/api/leagues/coverage": [],
  "/api/workers": [],
  "/api/unmatched": [],
  "/api/matches/with-odds": [],
  "/api/display/missing-team-names": [],
  "/api/display/translation-status": { done_league_seasons: ["1-2026"] },
  "/api/recommendation-records": [],
  "/api/oddspapi/backfill-audit?season=2025": {
    generated_at: "2026-05-30T10:00:00+08:00",
    league_summaries: [],
    season: 2025,
    totals: {
      failed_matches: 0,
      finished_matches: 0,
      matched_matches: 0,
      snapshot_matches: 0,
      unmatched_matches: 0
    },
    worker_progress: null
  },
  "/api/training/workspace": {
    dataset: { column_count: 0, exists: false, path: "x", row_count: 0, size_bytes: 0, updated_at: null },
    dataset_report: { exists: false, path: "x", size_bytes: 0, updated_at: null },
    market_baseline: { exists: false, path: "x" },
    qa: { exists: false, path: "x" }
  },
  "/api/match-list/workspace": {
    filters: {
      league_name: null,
      odds_filter: "all",
      search: null,
      status_filter: "all",
      time_preset: "next_24h"
    },
    freshness: {
      latest_match_updated_at: null,
      latest_odds_updated_at: null,
      latest_fixtures_results_sync: null,
      latest_odds_sync: null
    },
    leagues: [],
    matches: [],
    total_matches: 0
  }
};

describe("apiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads only lightweight dashboard data on initial page load", async () => {
    const fetchMock = vi.fn(async (rawUrl: string) => {
      const url = rawUrl.replace(/^http:\/\/127\.0\.0\.1:\d+/, "");
      return Response.json(apiPayloads[url]);
    });
    vi.stubGlobal("fetch", fetchMock);

    const data = await loadDashboardData();

    expect(data.source).toBe("api");
    expect(data.summary.total_matches).toBe(3);
    expect(data.doneDisplayTranslationKeys).toEqual(["1-2026"]);
    expect(fetchMock).not.toHaveBeenCalledWith("/api/training/workspace");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/paper-recommendations/workspace");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/match-list/workspace");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/oddspapi/backfill-audit?season=2025");
  });

  it("keeps local dashboard data when one secondary core endpoint fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (rawUrl: string) => {
        const url = rawUrl.replace(/^http:\/\/127\.0\.0\.1:\d+/, "");
        if (url === "/api/recommendation-records") {
          return new Response("records endpoint failed", { status: 500 });
        }
        return Response.json(apiPayloads[url]);
      })
    );

    const data = await loadDashboardData();

    expect(data.source).toBe("api");
    expect(data.summary.total_matches).toBe(3);
    expect(data.recommendationRecords).toEqual([]);
  });

  it("falls back only for the requested optional workspace", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("paper endpoint failed", { status: 500 }))
    );

    const workspace = await loadPaperRecommendationWorkspace();

    expect(workspace.summary.total_records).toBeGreaterThan(0);
  });
});
