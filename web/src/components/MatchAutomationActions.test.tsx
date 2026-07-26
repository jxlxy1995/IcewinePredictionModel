import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MatchAutomationActions } from "./MatchAutomationActions";

describe("MatchAutomationActions", () => {
  it("renders manual and filtered task actions", () => {
    const html = renderToStaticMarkup(
      <MatchAutomationActions
        isBusy={false}
        onCreateFiltered={vi.fn()}
        onCreateManual={vi.fn()}
      />
    );

    expect(html).toContain("创建自动任务");
    expect(html).toContain("一键创建筛选任务");
    expect(html).not.toContain("disabled");
  });

  it("disables both actions while a match-list operation is running", () => {
    const html = renderToStaticMarkup(
      <MatchAutomationActions
        isBusy
        onCreateFiltered={vi.fn()}
        onCreateManual={vi.fn()}
      />
    );

    expect((html.match(/disabled/g) ?? []).length).toBe(2);
  });
});
