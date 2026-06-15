import { describe, expect, it } from "vitest";

import {
  buildPaperAutomationSummary,
  formatAutomationStatus,
  formatAutomationWindow,
  formatNotificationStatus
} from "./paperAutomationWorkspace";
import type { PaperAutomationTask } from "./types";

function task(overrides: Partial<PaperAutomationTask>): PaperAutomationTask {
  return {
    id: 1,
    created_by: "tester",
    created_at: "2026-06-15T00:00:00",
    updated_at: "2026-06-15T00:00:00",
    trigger_at: "2026-06-15T10:00:00",
    match_window_start: "2026-06-15T12:00:00",
    match_window_end: "2026-06-15T18:00:00",
    started_at: null,
    finished_at: null,
    missed_at: null,
    cancelled_at: null,
    status: "pending",
    notification_status: "pending",
    notification_error: null,
    error_message: null,
    target_match_count: 0,
    result_payload: null,
    ...overrides
  };
}

describe("paper automation workspace", () => {
  it("summarizes task queue status for console metrics", () => {
    const today = "2026-06-15T08:00:00";
    const summary = buildPaperAutomationSummary(
      [
        task({ id: 1, status: "pending" }),
        task({ id: 2, status: "running" }),
        task({ id: 3, status: "success", finished_at: "2026-06-15T06:30:00" }),
        task({ id: 4, status: "success", finished_at: "2026-06-14T23:30:00" }),
        task({ id: 5, status: "failed", notification_status: "sent" }),
        task({ id: 6, status: "success", notification_status: "failed" })
      ],
      today
    );

    expect(summary).toEqual({
      pending: 1,
      running: 1,
      completedToday: 1,
      failedOrNotificationFailed: 2
    });
  });

  it("formats backend status values for display", () => {
    expect(formatAutomationStatus("pending")).toBe("待执行");
    expect(formatAutomationStatus("running")).toBe("执行中");
    expect(formatAutomationStatus("success")).toBe("成功");
    expect(formatAutomationStatus("failed")).toBe("失败");
    expect(formatAutomationStatus("missed")).toBe("已错过");
    expect(formatAutomationStatus("cancelled")).toBe("已取消");
    expect(formatAutomationStatus("custom")).toBe("custom");

    expect(formatNotificationStatus("pending")).toBe("待推送");
    expect(formatNotificationStatus("not_configured")).toBe("未配置");
    expect(formatNotificationStatus("sent")).toBe("已发送");
    expect(formatNotificationStatus("failed")).toBe("失败");
  });

  it("formats task match windows compactly", () => {
    expect(formatAutomationWindow(task({}))).toBe("2026-06-15 12:00 - 2026-06-15 18:00");
  });
});
