import { describe, expect, it } from "vitest";

import type { OddspapiBackfillAudit } from "./types";
import { mockOddspapiBackfillAudit } from "./mockData";
import {
  buildOddspapiAuditSummaryCards,
  formatOddspapiStatusLabel,
  listOddspapiLeagueAuditRows
} from "./oddspapiBackfillAuditWorkspace";

const audit: OddspapiBackfillAudit = {
  season: 2025,
  log_dir: "logs/odds",
  worker_progress: {
    status: "running",
    mode: "balanced",
    season: 2025,
    updated_at: "2026-05-27T10:15:00+08:00",
    current_league_id: "40",
    current_league_name: "Championship",
    current_league_display_name: "英冠",
    round: 12,
    processed_matches: 18,
    inserted_snapshots: 540,
    failed_matches: 2,
    requests_used: 31,
    total_processed_matches: 180,
    total_inserted_snapshots: 5400,
    total_failed_matches: 12,
    total_requests_used: 310
  },
  league_summaries: [
    {
      league_name: "Championship",
      league_display_name: "英冠",
      source_league_id: "40",
      finished_matches: 46,
      matched_matches: 40,
      snapshot_matches: 32,
      snapshot_count: 960,
      asian_handicap_snapshot_count: 480,
      total_goals_snapshot_count: 480,
      status_counts: { unmatched: 4, failed: 2 },
      error_counts: { "team-name-mismatch": 3 }
    },
    {
      league_name: "League One",
      league_display_name: "英甲",
      source_league_id: "41",
      finished_matches: 46,
      matched_matches: 44,
      snapshot_matches: 44,
      snapshot_count: 1320,
      asian_handicap_snapshot_count: 660,
      total_goals_snapshot_count: 660,
      status_counts: { success: 44 },
      error_counts: {}
    }
  ]
};

describe("oddspapi backfill audit workspace helpers", () => {
  it("builds summary cards from worker totals", () => {
    expect(buildOddspapiAuditSummaryCards(audit)).toEqual([
      { label: "当前联赛", value: "英冠" },
      { label: "已处理比赛", value: "180" },
      { label: "赔率快照", value: "5,400" },
      { label: "失败比赛", value: "12" }
    ]);
  });

  it("sorts league rows by unmatched or failed volume first", () => {
    const rows = listOddspapiLeagueAuditRows(audit);

    expect(rows.map((row) => row.league_display_name)).toEqual(["英冠", "英甲"]);
    expect(rows[0].issue_count).toBe(6);
    expect(rows[0].snapshot_coverage_ratio).toBe("0.6957");
    expect(rows[1].status_summary).toBe("成功 44");
  });

  it("formats known Oddspapi backfill statuses", () => {
    expect(formatOddspapiStatusLabel("success")).toBe("成功");
    expect(formatOddspapiStatusLabel("unmatched")).toBe("匹配失败");
    expect(formatOddspapiStatusLabel("unavailable")).toBe("不可用");
    expect(formatOddspapiStatusLabel("custom")).toBe("custom");
  });

  it("keeps mock audit league display names readable in Chinese", () => {
    expect(buildOddspapiAuditSummaryCards(mockOddspapiBackfillAudit)[0]).toEqual({
      label: "当前联赛",
      value: "英冠"
    });
    expect(
      listOddspapiLeagueAuditRows(mockOddspapiBackfillAudit).map(
        (row) => row.league_display_name
      )
    ).toEqual(["英冠", "英超", "德甲"]);
  });
});
