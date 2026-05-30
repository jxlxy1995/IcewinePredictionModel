import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadDashboardData,
  loadLatestTrainingRun,
  loadMatchListWorkspace,
  loadPaperRecommendationWorkspace,
  startTrainingFullRefresh
} from "./apiClient";

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
    qa: { exists: false, path: "x" },
    latest_run: null
  },
  "/api/training/runs/latest": {
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
    artifact_paths: {}
  },
  "/api/match-list/workspace": {
    filters: {
      end_time: "2026-05-31T12:00:00+08:00",
      league_name: null,
      odds_filter: "all",
      search: null,
      start_time: "2026-05-30T00:00:00+08:00",
      status_filter: "all"
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

  it("loads latest training run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (rawUrl: string) => {
        const url = rawUrl.replace(/^http:\/\/127\.0\.0\.1:\d+/, "");
        return Response.json(apiPayloads[url]);
      })
    );

    const run = await loadLatestTrainingRun();

    expect(run?.snapshot_tag).toBe("20260530-1323");
  });

  it("starts training full refresh", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        id: 4,
        run_type: "full_refresh",
        status: "running",
        started_at: "2026-05-30T13:23:00+08:00",
        finished_at: null,
        snapshot_tag: "20260530-1323",
        current_step: "queued",
        error_step: null,
        error_message: null,
        dataset_rows: null,
        eligible_matches: null,
        complete_matches: null,
        coverage_ratio: null,
        last_trained_match_id: null,
        last_trained_match_summary: null,
        last_trained_kickoff_time: null,
        new_complete_matches: null,
        artifact_paths: {}
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const run = await startTrainingFullRefresh();

    expect(fetchMock).toHaveBeenCalledWith("/api/training/runs/full-refresh", {
      body: "{}",
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    expect(run.status).toBe("running");
  });

  it("loads match list workspace with explicit datetime range", async () => {
    const fetchMock = vi.fn(async () => Response.json(apiPayloads["/api/match-list/workspace"]));
    vi.stubGlobal("fetch", fetchMock);

    const workspace = await loadMatchListWorkspace({
      end_time: "2026-05-31T12:00",
      league_name: "J1 League",
      start_time: "2026-05-30T00:00",
      status_filter: "live"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/match-list/workspace?end_time=2026-05-31T12%3A00&league_name=J1+League&start_time=2026-05-30T00%3A00&status_filter=live"
    );
    expect(workspace.filters.start_time).toBe("2026-05-30T00:00:00+08:00");
  });
});
