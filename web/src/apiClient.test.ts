import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createManualExecutionTimepointOdds,
  createPaperAutomationTask,
  cancelPaperAutomationTask,
  loadDashboardData,
  loadLatestTrainingRun,
  loadMatchListWorkspace,
  loadMatchSyncRunDetail,
  loadPaperAutomationTask,
  loadPaperAutomationTasks,
  loadPaperRecommendationWorkspace,
  recordPaperCandidates,
  startTrainingFullRefresh,
  syncFixtureRange,
  syncFilteredMatchListFixturesResults,
  syncSingleMatchOdds
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
  "/api/display/team-name-workspaces": [
    {
      league_id: 49,
      league_name: "World Cup (World)",
      league_display_name: "世界杯",
      country_or_region: "World",
      season: 2026,
      team_count: 48,
      match_count: 72,
      latest_kickoff_time: "2026-06-28T18:00:00+08:00"
    }
  ],
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
  "/api/paper-recommendations/workspace": {
    strategies: [],
    candidates: [],
    records: [],
    summary: {
      total_records: 12,
      pending_records: 2,
      settled_records: 10,
      void_records: 0,
      candidate_count: 0,
      total_stake_units: "10.00",
      total_profit_units: "1.140",
      hit_rate: "0.6000",
      roi: "0.1140"
    },
    groups: {
      by_strategy: [],
      by_league: [],
      by_line_bucket: [],
      by_manual_adjustment: []
    }
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
    expect(data.teamDisplayWorkspaces).toEqual(apiPayloads["/api/display/team-name-workspaces"]);
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

  it("throws paper workspace API failures instead of returning mock data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("paper endpoint failed", { status: 500 }))
    );

    await expect(loadPaperRecommendationWorkspace()).rejects.toThrow(
      "paper endpoint failed"
    );
  });

  it("loads paper workspace with replay window params", async () => {
    const fetchMock = vi.fn(async (rawUrl: string) => {
      const url = rawUrl.replace(/^http:\/\/127\.0\.0\.1:\d+/, "");
      return Response.json(apiPayloads["/api/paper-recommendations/workspace"]);
    });
    vi.stubGlobal("fetch", fetchMock);

    await loadPaperRecommendationWorkspace({
      end_time: "2026-05-30T23:59",
      start_time: "2026-05-30T00:00"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/paper-recommendations/workspace?end_time=2026-05-30T23%3A59&start_time=2026-05-30T00%3A00"
    );
  });

  it("records paper candidates with one batch request", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json(apiPayloads["/api/paper-recommendations/workspace"])
    );
    vi.stubGlobal("fetch", fetchMock);

    await recordPaperCandidates(
      [
        { match_id: 17446, strategy_key: "asian_away_cover_hgb_edge_v1" },
        { match_id: 17446, strategy_key: "asian_away_cover_hgb_bucket_v2" }
      ],
      {
        end_time: "2026-05-30T23:59",
        start_time: "2026-05-30T00:00"
      }
    );

    expect(fetchMock).toHaveBeenCalledWith("/api/paper-recommendations/records/batch", {
      body: JSON.stringify({
        candidates: [
          { match_id: 17446, strategy_key: "asian_away_cover_hgb_edge_v1" },
          { match_id: 17446, strategy_key: "asian_away_cover_hgb_bucket_v2" }
        ],
        end_time: "2026-05-30T23:59",
        start_time: "2026-05-30T00:00"
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
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
      odds_filter: ["none", "near"],
      start_time: "2026-05-30T00:00",
      status_filter: "live"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/match-list/workspace?end_time=2026-05-31T12%3A00&league_name=J1+League&odds_filter=none%2Cnear&start_time=2026-05-30T00%3A00&status_filter=live"
    );
    expect(workspace.filters.start_time).toBe("2026-05-30T00:00:00+08:00");
  });

  it("syncs filtered match fixtures with full filter payload", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        sync_run: {
          id: 1,
          sync_type: "fixtures_results",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          status: "success",
          days: 0,
          created_count: 1,
          updated_count: 0,
          skipped_count: 0,
          requests_used: 1,
          error_message: null
        },
        report: {
          sync_type: "fixtures_results",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          target_count: 1,
          success_count: 1,
          failed_count: 0,
          skipped_count: 0,
          requests_used: 1,
          success: [],
          failed: [],
          skipped: []
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await syncFilteredMatchListFixturesResults({
      end_time: "2026-05-31T12:00",
      league_name: "J1 League",
      odds_filter: ["pending_fill", "none"],
      search: "hiro",
      start_time: "2026-05-30T00:00",
      status_filter: "not_started"
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/match-list/sync/fixtures-results", {
      body: JSON.stringify({
        end_time: "2026-05-31T12:00",
        league_name: "J1 League",
        odds_filter: "pending_fill,none",
        search: "hiro",
        start_time: "2026-05-30T00:00",
        status_filter: "not_started"
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });

  it("syncs fixture range with current time filters", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        sync_run: {
          id: 1,
          sync_type: "fixtures_range",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          status: "success",
          days: 0,
          created_count: 3,
          updated_count: 2,
          skipped_count: 0,
          requests_used: 2,
          error_message: null
        },
        report: {
          sync_type: "fixtures_range",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          target_count: 5,
          success_count: 5,
          failed_count: 0,
          skipped_count: 0,
          requests_used: 2,
          created_count: 3,
          updated_count: 2,
          success: [],
          failed: [],
          skipped: []
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await syncFixtureRange({
      end_time: "2026-05-31T12:00",
      league_name: "J1 League",
      start_time: "2026-05-30T00:00"
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/match-list/sync/fixtures-range", {
      body: JSON.stringify({
        end_time: "2026-05-31T12:00",
        league_name: "J1 League",
        start_time: "2026-05-30T00:00"
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });

  it("syncs single match odds by path id", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        sync_run: {
          id: 1,
          sync_type: "odds",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          status: "success",
          days: 0,
          created_count: 1,
          updated_count: 0,
          skipped_count: 0,
          requests_used: 1,
          error_message: null
        },
        report: {
          sync_type: "odds",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          target_count: 1,
          success_count: 1,
          failed_count: 0,
          skipped_count: 0,
          requests_used: 1,
          success: [],
          failed: [],
          skipped: []
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await syncSingleMatchOdds(16356);

    expect(fetchMock).toHaveBeenCalledWith("/api/matches/16356/sync/odds", {
      body: "{}",
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });

  it("creates manual execution timepoint odds with match id path", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        inserted_count: 2,
        message: "manual execution timepoint odds created",
        snapshot_time: "2026-05-30T12:40:00+08:00",
        status: "created"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createManualExecutionTimepointOdds(16356, {
      market_line: "-0.50",
      market_type: "asian_handicap",
      odds_by_side: { away: "1.96", home: "1.90" },
      target_minutes_before_kickoff: 20
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/matches/16356/execution-timepoint-odds/manual",
      {
        body: JSON.stringify({
          market_line: "-0.50",
          market_type: "asian_handicap",
          odds_by_side: { away: "1.96", home: "1.90" },
          target_minutes_before_kickoff: 20
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST"
      }
    );
    expect(result.status).toBe("created");
  });

  it("loads paper automation tasks", async () => {
    const fetchMock = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", fetchMock);

    const tasks = await loadPaperAutomationTasks();

    expect(fetchMock).toHaveBeenCalledWith("/api/paper-automation/tasks");
    expect(tasks).toEqual([]);
  });

  it("creates paper automation task with scheduling payload", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        id: 12,
        created_by: "web",
        created_at: "2026-05-20T20:00:00+08:00",
        updated_at: "2026-05-20T20:00:00+08:00",
        trigger_at: "2026-05-20T21:00:00+08:00",
        match_window_start: "2026-05-20T21:30:00+08:00",
        match_window_end: "2026-05-20T22:30:00+08:00",
        started_at: null,
        finished_at: null,
        missed_at: null,
        cancelled_at: null,
        status: "pending",
        notification_status: "pending",
        notification_error: null,
        error_message: null,
        target_match_count: 1,
        result_payload: null
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const task = await createPaperAutomationTask({
      trigger_at: "2026-05-20T21:00:00+08:00",
      match_window_start: "2026-05-20T21:30:00+08:00",
      match_window_end: "2026-05-20T22:30:00+08:00"
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/paper-automation/tasks", {
      body: JSON.stringify({
        trigger_at: "2026-05-20T21:00:00+08:00",
        match_window_start: "2026-05-20T21:30:00+08:00",
        match_window_end: "2026-05-20T22:30:00+08:00"
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    expect(task.id).toBe(12);
    expect(task.status).toBe("pending");
  });

  it("loads and cancels paper automation task by id", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        id: 12,
        created_by: "web",
        created_at: "2026-05-20T20:00:00+08:00",
        updated_at: "2026-05-20T20:05:00+08:00",
        trigger_at: "2026-05-20T21:00:00+08:00",
        match_window_start: "2026-05-20T21:30:00+08:00",
        match_window_end: "2026-05-20T22:30:00+08:00",
        started_at: null,
        finished_at: null,
        missed_at: null,
        cancelled_at: "2026-05-20T20:05:00+08:00",
        status: "cancelled",
        notification_status: "pending",
        notification_error: null,
        error_message: null,
        target_match_count: 1,
        result_payload: null
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const task = await loadPaperAutomationTask(12);
    const cancelled = await cancelPaperAutomationTask(12);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/paper-automation/tasks/12");
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/paper-automation/tasks/12/cancel", {
      body: "{}",
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    expect(task.id).toBe(12);
    expect(cancelled.status).toBe("cancelled");
  });

  it("includes API error detail when match odds sync fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { detail: "UNIQUE constraint failed: historical_odds_raw_snapshots" },
          { status: 500 }
        )
      )
    );

    await expect(syncSingleMatchOdds(16356)).rejects.toThrow(
      "UNIQUE constraint failed: historical_odds_raw_snapshots"
    );
  });

  it("loads persisted match sync run detail", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        sync_run: {
          id: 7,
          sync_type: "odds",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          status: "success",
          days: 0,
          created_count: 1,
          updated_count: 0,
          skipped_count: 0,
          requests_used: 2,
          error_message: null
        },
        report: {
          sync_type: "odds",
          started_at: "2026-05-30T10:00:00+08:00",
          finished_at: "2026-05-30T10:01:00+08:00",
          target_count: 1,
          success_count: 0,
          failed_count: 1,
          skipped_count: 0,
          requests_used: 2,
          success: [],
          failed: [
            {
              match_id: 16359,
              kickoff_time: "2026-05-30T14:00:00+08:00",
              league_name: "J1 League",
              home_team_name: "Cerezo Osaka",
              away_team_name: "FC Tokyo",
              fixture: "Cerezo Osaka vs FC Tokyo",
              status: "failed",
              message: "未获取到可用赔率",
              created_count: 0,
              updated_count: 0,
              skipped_count: 0,
              requests_used: 0,
              source_fixture_id: "missing-fixture",
              diagnostic_status: "unavailable",
              diagnostic_error: "OddsPapi HTTP error: status=404",
              snapshot_count: 0
            }
          ],
          skipped: []
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const detail = await loadMatchSyncRunDetail(7);

    expect(fetchMock).toHaveBeenCalledWith("/api/data-sync-runs/7/items");
    expect(detail.report.failed[0].diagnostic_status).toBe("unavailable");
  });
});
