import { describe, expect, it } from "vitest";

import {
  buildPaperSnapshotReviewCards,
  buildPaperSnapshotReviewPresetRange,
  buildPaperSnapshotReviewRows,
  defaultPaperSnapshotReviewFilters,
  paperSnapshotReviewSourceOptions
} from "./paperSnapshotReviewWorkspace";
import type { PaperSnapshotReviewWorkspace } from "./types";

const workspace: PaperSnapshotReviewWorkspace = {
  filters: {
    from_date: "2026-05-01T00:00",
    to_date: "2026-06-23T23:59",
    snapshot_source: "historical_backfill",
    snapshot_version: "paper_confidence_v1"
  },
  deduplication: {
    applied: false,
    input_group_count: 850,
    selected_group_count: 850,
    excluded_group_count: 0
  },
  summary: {
    group_count: 850,
    settled_groups: 848,
    pending_groups: 2,
    suggested_stake_units: "904.50",
    flat_profit_units: "220.513",
    weighted_profit_units: "249.399",
    flat_roi: "0.2600",
    weighted_roi: "0.2757"
  },
  groups: {
    by_market_type: [
      {
        group_name: "asian_handicap",
        group_count: 378,
        settled_groups: 378,
        pending_groups: 0,
        suggested_stake_units: "549.50",
        flat_profit_units: "116.642",
        weighted_profit_units: "170.665",
        flat_roi: "0.3086",
        weighted_roi: "0.3106"
      }
    ],
    by_market_side: [],
    by_confidence_bucket: [],
    by_stake_bucket: [],
    by_stake_cap_reason: [],
    by_line_bucket: [],
    by_signal_family_combo: [],
    by_signal_count: [],
    by_league: [],
    by_snapshot_source: []
  },
  samples: {
    high_confidence_losses: [],
    low_stake_wins: [],
    pending: []
  }
};

describe("paperSnapshotReviewWorkspace", () => {
  it("builds summary cards with ROI percentages", () => {
    expect(buildPaperSnapshotReviewCards(workspace)).toEqual([
      { label: "快照组数", value: "850" },
      { label: "已结算", value: "848" },
      { label: "Pending", value: "2" },
      { label: "建议手数", value: "904.50" },
      { label: "Flat ROI", value: "26.00%" },
      { label: "Weighted ROI", value: "27.57%" }
    ]);
  });

  it("normalizes group rows for tables", () => {
    expect(buildPaperSnapshotReviewRows(workspace.groups.by_market_type)[0]).toMatchObject({
      groupName: "asian_handicap",
      groupCount: 378,
      weightedRoi: "31.06%",
      weightedProfitUnits: "170.665"
    });
  });

  it("defaults to May first through today", () => {
    expect(defaultPaperSnapshotReviewFilters(new Date(2026, 5, 24, 15, 0))).toEqual({
      from_date: "2026-05-01T00:00",
      to_date: "2026-06-24T23:59",
      snapshot_source: "historical_backfill"
    });
  });

  it("offers all snapshot sources without changing the default source", () => {
    expect(paperSnapshotReviewSourceOptions).toEqual([
      { label: "全部来源（All）", value: "all" },
      { label: "historical_backfill", value: "historical_backfill" },
      { label: "manual_record", value: "manual_record" },
      { label: "automation", value: "automation" }
    ]);
    expect(defaultPaperSnapshotReviewFilters(new Date(2026, 5, 24, 15, 0)).snapshot_source).toBe(
      "historical_backfill"
    );
  });

  it("adds the deduplicated count card only for all sources", () => {
    const allWorkspace = {
      ...workspace,
      filters: { ...workspace.filters, snapshot_source: "all" },
      deduplication: {
        applied: true,
        input_group_count: 852,
        selected_group_count: 850,
        excluded_group_count: 2
      }
    };

    expect(buildPaperSnapshotReviewCards(allWorkspace).at(-1)).toEqual({
      label: "去重排除",
      value: "2"
    });
    expect(buildPaperSnapshotReviewCards(workspace)).not.toContainEqual({
      label: "去重排除",
      value: "0"
    });
  });

  it("builds common preset ranges", () => {
    expect(buildPaperSnapshotReviewPresetRange("last7", new Date(2026, 5, 24, 15, 0))).toEqual({
      from_date: "2026-06-18T00:00",
      to_date: "2026-06-24T23:59"
    });
    expect(buildPaperSnapshotReviewPresetRange("thisMonth", new Date(2026, 5, 24, 15, 0))).toEqual({
      from_date: "2026-06-01T00:00",
      to_date: "2026-06-24T23:59"
    });
    expect(buildPaperSnapshotReviewPresetRange("lastMonth", new Date(2026, 5, 24, 15, 0))).toEqual({
      from_date: "2026-05-01T00:00",
      to_date: "2026-05-31T23:59"
    });
  });
});
