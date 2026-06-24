import { describe, expect, it } from "vitest";

import {
  dashboardNavItems,
  initialDashboardView,
  shouldAutoLoadLazyView
} from "./pages/DashboardPage";
import { mockDashboardData } from "./mockData";

describe("dashboard navigation", () => {
  it("keeps only active workflow pages in the sidebar", () => {
    expect(dashboardNavItems.map((item) => item.key)).toEqual([
      "matchList",
      "automationTasks",
      "displayNames",
      "models",
      "paperTracking",
      "paperSnapshotReview",
      "records"
    ]);
  });

  it("opens the match list by default", () => {
    expect(initialDashboardView).toBe("matchList");
  });

  it("does not show mocked recommendation records", () => {
    expect(mockDashboardData.recommendationRecords).toEqual([]);
  });

  it("loads review pages that should show persisted data on first open", () => {
    expect(shouldAutoLoadLazyView("paperTracking")).toBe(false);
    expect(shouldAutoLoadLazyView("paperSnapshotReview")).toBe(true);
    expect(shouldAutoLoadLazyView("automationTasks")).toBe(true);
    expect(shouldAutoLoadLazyView("matchList")).toBe(true);
    expect(shouldAutoLoadLazyView("models")).toBe(true);
  });
});
