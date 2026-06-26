import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PaperConfidenceSimulationTable } from "./components/PaperRecommendationTables";
import { mockPaperRecommendationWorkspace } from "./mockData";
import type { PaperRecommendationWorkspace } from "./types";

function workspaceWithConfidenceSimulation(): PaperRecommendationWorkspace {
  return {
    ...mockPaperRecommendationWorkspace,
    confidence_simulation: {
      summary: {
        group_count: 1,
        settled_groups: 1,
        suggested_stake_units: "1.00",
        flat_profit_units: "0.440",
        weighted_profit_units: "0.440",
        flat_roi: "0.4400",
        weighted_roi: "0.4400"
      },
      groups: [
        {
          group_key: "17446:asian_handicap:away_cover",
          match_id: 17446,
          source_match_id: "17446",
          kickoff_time: "2026-05-30T02:45:00+08:00",
          league_name: "Premier Division",
          league_display_name: "Ireland",
          home_team_name: "Drogheda United",
          home_team_display_name: "Drogheda",
          home_score: 1,
          away_team_name: "Waterford",
          away_team_display_name: "Waterford",
          away_score: 1,
          market_type: "asian_handicap",
          logical_side: "away_cover",
          recommendation_text: "Away +0.25",
          representative_record_id: 1,
          representative_strategy_key: "asian_away_cover_hgb_edge_v1",
          representative_market_line: "-0.25",
          representative_odds: "1.880",
          signal_record_ids: [1],
          triggered_strategy_keys: ["asian_away_cover_hgb_edge_v1"],
          triggered_strategy_display_names: ["Asian away HGB edge v1"],
          signal_families: ["asian_away_hgb"],
          confidence_score: 72,
          suggested_stake_units: "1.00",
          stake_cap_reason: "none",
          status: "settled",
          settlement_result: "half_win",
          flat_profit_units: "0.440",
          weighted_profit_units: "0.440",
          warning: null
        }
      ],
      by_score_bucket: [],
      by_stake_bucket: [],
      by_family_combo: []
    }
  };
}

describe("PaperConfidenceSimulationTable", () => {
  it("renders compact red delete buttons for expanded signal records", () => {
    const onDelete = vi.fn();
    const workspace = workspaceWithConfidenceSimulation();
    const groupKey = workspace.confidence_simulation!.groups[0].group_key;

    const html = renderToStaticMarkup(
      <PaperConfidenceSimulationTable
        defaultExpandedGroupKeys={[groupKey]}
        isBusy={false}
        onDelete={onDelete}
        workspace={workspace}
      />
    );

    expect((html.match(/paper-delete-button/g) ?? []).length).toBe(2);
    expect(html).toContain("paper-row-actions-cell");
    expect(html).toContain('aria-label="delete paper record #1"');
  });
});
