import { describe, expect, it } from "vitest";

import type { ModelTrainingOverview } from "./types";
import {
  buildModelTrainingSummaryCards,
  formatModelTrainingStatus,
  listRecentModelRuns
} from "./modelTrainingWorkspace";

const overview: ModelTrainingOverview = {
  generated_at: "2026-05-26T11:45:00+08:00",
  total_training_matches: 1844,
  total_training_snapshots: 183204,
  model_runs: [
    {
      model_name: "Skellam",
      model_version: "skellam-margin-v1",
      status: "ready",
      trained_at: "2026-05-25T21:20:00+08:00",
      sample_count: 1420,
      league_count: 28,
      market_types: ["asian_handicap"],
      validation_log_loss: "0.6812",
      validation_brier_score: "0.2134"
    },
    {
      model_name: "Dixon-Coles",
      model_version: "dixon-coles-attack-defense-v1",
      status: "training",
      trained_at: "2026-05-26T10:30:00+08:00",
      sample_count: 1844,
      league_count: 42,
      market_types: ["score_distribution", "asian_handicap", "total_goals"],
      validation_log_loss: "0.6541",
      validation_brier_score: "0.1988"
    }
  ],
  league_training_coverage: [
    {
      league_name: "Premier League",
      league_display_name: "英超",
      season: 2025,
      finished_matches: 380,
      training_matches: 350,
      coverage_ratio: "0.9211"
    },
    {
      league_name: "Liga I",
      league_display_name: "罗甲",
      season: 2025,
      finished_matches: 240,
      training_matches: 18,
      coverage_ratio: "0.0750"
    }
  ]
};

describe("model training workspace helpers", () => {
  it("builds model training summary cards from overview data", () => {
    expect(buildModelTrainingSummaryCards(overview)).toEqual([
      { label: "训练样本", value: "1,844" },
      { label: "赔率快照", value: "183,204" },
      { label: "模型版本", value: "2" },
      { label: "可出结果", value: "1" }
    ]);
  });

  it("sorts recent model runs by training time descending", () => {
    expect(listRecentModelRuns(overview).map((run) => run.model_name)).toEqual([
      "Dixon-Coles",
      "Skellam"
    ]);
  });

  it("formats model training status for display", () => {
    expect(formatModelTrainingStatus("ready")).toBe("可用");
    expect(formatModelTrainingStatus("training")).toBe("训练中");
    expect(formatModelTrainingStatus("failed")).toBe("失败");
  });
});
