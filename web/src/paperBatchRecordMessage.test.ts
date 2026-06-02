import { describe, expect, it } from "vitest";

import {
  formatPaperBatchRecordMessage,
  formatPaperSingleRecordMessage
} from "./paperBatchRecordMessage";

describe("paper batch record messages", () => {
  it("summarizes created and skipped batch records", () => {
    expect(
      formatPaperBatchRecordMessage({
        created_count: 1,
        requested_count: 3,
        skipped: [],
        skipped_count: 2
      })
    ).toBe("已记录 1 条纸面观察，跳过 2 条");
  });

  it("uses the duplicate skip reason for single record attempts", () => {
    expect(
      formatPaperSingleRecordMessage({
        created_count: 0,
        requested_count: 1,
        skipped: [
          {
            match_id: 17446,
            reason: "duplicate active paper recommendation record",
            strategy_key: "asian_away_cover_hgb_edge_v1"
          }
        ],
        skipped_count: 1
      })
    ).toBe("已跳过：该纸面观察已记录");
  });
});
