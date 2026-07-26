import { describe, expect, it } from "vitest";

import {
  formatFilteredAutomationResult,
  mergePaperAutomationTasks
} from "./paperAutomationBatch";
import type { PaperAutomationTask } from "./types";

function task(id: number): PaperAutomationTask {
  return {
    id,
    created_by: "web",
    created_at: "2026-07-27T17:00:00+08:00",
    updated_at: "2026-07-27T17:00:00+08:00",
    trigger_at: "2026-07-27T17:51:00+08:00",
    match_window_start: "2026-07-27T18:00:00+08:00",
    match_window_end: "2026-07-27T18:00:00+08:00",
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
  };
}

describe("filtered paper automation batch helpers", () => {
  it("formats created, skipped, and excluded counts", () => {
    expect(
      formatFilteredAutomationResult({
        matched_match_count: 12,
        excluded_match_count: 1,
        eligible_match_count: 11,
        time_slot_count: 4,
        created_count: 2,
        skipped_existing_count: 1,
        skipped_expired_count: 1,
        tasks: [task(2), task(3)]
      })
    ).toBe(
      "筛选 12 场比赛、4 个时间段：创建 2 个任务，已有任务跳过 1 个，已过 T-9 跳过 1 个，黑名单排除 1 场"
    );
  });

  it("omits the blacklist clause when no matches were excluded", () => {
    expect(
      formatFilteredAutomationResult({
        matched_match_count: 0,
        excluded_match_count: 0,
        eligible_match_count: 0,
        time_slot_count: 0,
        created_count: 0,
        skipped_existing_count: 0,
        skipped_expired_count: 0,
        tasks: []
      })
    ).toBe(
      "筛选 0 场比赛、0 个时间段：创建 0 个任务，已有任务跳过 0 个，已过 T-9 跳过 0 个"
    );
  });

  it("prepends created tasks without duplicate ids", () => {
    expect(
      mergePaperAutomationTasks([task(1), task(2)], [task(2), task(3)]).map(
        (row) => row.id
      )
    ).toEqual([2, 3, 1]);
  });
});
