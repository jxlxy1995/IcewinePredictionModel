import { describe, expect, it } from "vitest";

import { dashboardNavItems, initialDashboardView } from "./pages/DashboardPage";
import { mockDashboardData } from "./mockData";

describe("dashboard navigation", () => {
  it("keeps only active workflow pages in the sidebar", () => {
    expect(dashboardNavItems.map((item) => item.label)).toEqual([
      "比赛列表",
      "中文名",
      "模型训练",
      "纸面跟踪",
      "推荐记录"
    ]);
  });

  it("opens the match list by default", () => {
    expect(initialDashboardView).toBe("matchList");
  });

  it("does not show mocked recommendation records", () => {
    expect(mockDashboardData.recommendationRecords).toEqual([]);
  });
});
