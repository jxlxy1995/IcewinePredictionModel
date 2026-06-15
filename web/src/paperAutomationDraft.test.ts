import { describe, expect, it } from "vitest";

import { updateDraftFromTriggerTime } from "./paperAutomationDraft";

describe("paper automation draft helpers", () => {
  it("sets both match window fields to nine minutes after trigger time", () => {
    const draft = {
      trigger_at: "",
      match_window_start: "2026-06-15T20:00",
      match_window_end: "2026-06-15T21:00"
    };

    expect(updateDraftFromTriggerTime(draft, "2026-06-15T23:21")).toEqual({
      trigger_at: "2026-06-15T23:21",
      match_window_start: "2026-06-15T23:30",
      match_window_end: "2026-06-15T23:30"
    });
  });

  it("handles hour and day rollover", () => {
    const draft = {
      trigger_at: "",
      match_window_start: "",
      match_window_end: ""
    };

    expect(updateDraftFromTriggerTime(draft, "2026-06-15T23:55")).toEqual({
      trigger_at: "2026-06-15T23:55",
      match_window_start: "2026-06-16T00:04",
      match_window_end: "2026-06-16T00:04"
    });
  });
});
