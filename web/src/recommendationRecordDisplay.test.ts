import { describe, expect, it } from "vitest";

import {
  buildPagination,
  formatScore,
  paginateRecords,
  settlementTone,
  sortRecordsByKickoffDesc
} from "./recommendationRecordDisplay";

describe("recommendationRecordDisplay", () => {
  const records = [
    { id: 1, kickoff_time: "2026-05-30T01:00:00+08:00" },
    { id: 2, kickoff_time: "2026-05-31T01:00:00+08:00" },
    { id: 3, kickoff_time: "2026-05-31T01:00:00+08:00" }
  ];

  it("sorts records by kickoff time descending then id descending", () => {
    expect(sortRecordsByKickoffDesc(records).map((record) => record.id)).toEqual([3, 2, 1]);
  });

  it("formats score only when both scores are present", () => {
    expect(formatScore(2, 1)).toBe("2-1");
    expect(formatScore(null, 1)).toBe("vs");
    expect(formatScore(undefined, undefined)).toBe("vs");
  });

  it("maps settlement results to distinct tones", () => {
    expect(settlementTone("win")).toBe("win");
    expect(settlementTone("half_win")).toBe("half-win");
    expect(settlementTone("push")).toBe("push");
    expect(settlementTone("half_loss")).toBe("half-loss");
    expect(settlementTone("loss")).toBe("loss");
    expect(settlementTone(null)).toBe("pending");
  });

  it("paginates records and clamps page numbers", () => {
    const page = buildPagination({ totalItems: 45, page: 9, pageSize: 20 });
    expect(page).toEqual({ page: 3, pageCount: 3, pageSize: 20, totalItems: 45 });
    expect(paginateRecords(records, page).map((record) => record.id)).toEqual([]);
    const firstPage = buildPagination({ totalItems: 45, page: 1, pageSize: 20 });
    expect(paginateRecords(records, firstPage).map((record) => record.id)).toEqual([1, 2, 3]);
  });
});
