import { describe, expect, it } from "vitest";

import type { TrainingWorkspace } from "./types";
import {
  buildTrainingRunCards,
  buildTrainingWorkspaceCards,
  formatTrainingRunStatus,
  formatTrainingRunStep,
  listTrainingMarketRows
} from "./modelTrainingWorkspace";

const trainingWorkspace: TrainingWorkspace = {
  dataset: {
    exists: true,
    path: "local_data/training/baseline_main_leagues_20260529.csv",
    updated_at: "2026-05-29T18:10:00",
    size_bytes: 1441170,
    row_count: 5330,
    column_count: 42
  },
  dataset_report: {
    exists: true,
    path: "docs/数据审计/20260529-baseline-training-dataset.md",
    updated_at: "2026-05-29T18:10:00",
    size_bytes: 1200
  },
  qa: {
    exists: true,
    path: "docs/数据审计/20260529-baseline-training-dataset-qa.md",
    updated_at: "2026-05-29T18:20:00",
    empty_required_cells: 0,
    invalid_odds_cells: 0,
    invalid_probability_cells: 0,
    invalid_overround_cells: 0,
    thin_history_count: 152,
    thin_history_ratio: "0.0285",
    low_sample_leagues: { "Ykkosliiga (Finland)": 29 }
  },
  market_baseline: {
    exists: true,
    path: "docs/模型实验/20260529-close-market-baseline-evaluation.md",
    updated_at: "2026-05-29T18:30:00",
    market_samples: 15990,
    evaluated_market_samples: 15326,
    skipped_market_samples: 664,
    market_reports: {
      asian_handicap: {
        evaluated_count: 4928,
        skipped_count: 402,
        accuracy: "0.5244",
        log_loss: "0.6921",
        brier: "0.4412",
        overround: "1.0273",
        flat_bet_profit_units: "-92.6695",
        flat_bet_roi: "-0.0188",
        predicted_side_counts: { home: 2527, away: 2401 }
      },
      total_goals: {
        evaluated_count: 5068,
        skipped_count: 262,
        accuracy: "0.5199",
        log_loss: "0.6924",
        brier: "0.4474",
        overround: "1.0320",
        flat_bet_profit_units: "-111.2930",
        flat_bet_roi: "-0.0220",
        predicted_side_counts: { over: 2560, under: 2508 }
      },
      match_winner: {
        evaluated_count: 5330,
        skipped_count: 0,
        accuracy: "0.5032",
        log_loss: "1.0055",
        brier: "0.6015",
        overround: "1.0390",
        flat_bet_profit_units: "-190.4020",
        flat_bet_roi: "-0.0357",
        predicted_side_counts: { home: 3608, away: 1690, draw: 32 }
      }
    }
  },
  latest_run: null
};

describe("model training workspace helpers", () => {
  it("builds training workspace cards from workflow state", () => {
    expect(buildTrainingWorkspaceCards(trainingWorkspace)).toEqual([
      { label: "训练集样本", value: "5,330" },
      { label: "数据质量问题", value: "0" },
      { label: "Thin history", value: "152" },
      { label: "市场基准样本", value: "15,326" }
    ]);
  });

  it("lists market baseline rows with display names", () => {
    const rows = listTrainingMarketRows(trainingWorkspace);

    expect(rows.map((row) => row.marketLabel)).toEqual(["亚盘", "大小球", "胜平负"]);
    expect(rows[0].flatBetRoi).toBe("-0.0188");
  });

  it("formats latest training run cards", () => {
    const cards = buildTrainingRunCards({
      id: 3,
      run_type: "full_refresh",
      status: "success",
      started_at: "2026-05-30T13:23:00+08:00",
      finished_at: "2026-05-30T13:28:00+08:00",
      snapshot_tag: "20260530-1323",
      current_step: "finalize",
      error_step: null,
      error_message: null,
      dataset_rows: 5330,
      eligible_matches: 5981,
      complete_matches: 5330,
      coverage_ratio: "0.8912",
      last_trained_match_id: 177,
      last_trained_match_summary: "日职联 神户胜利船 1-0 鹿岛鹿角",
      last_trained_kickoff_time: "2026-05-30T18:00:00+08:00",
      new_complete_matches: null,
      artifact_paths: {}
    });

    expect(cards).toContainEqual({ label: "最近更新", value: "2026-05-30 13:28" });
    expect(cards).toContainEqual({ label: "训练样本", value: "5,330" });
    expect(cards).toContainEqual({ label: "最后入训", value: "日职联 神户胜利船 1-0 鹿岛鹿角" });
  });

  it("formats last trained kickoff time card", () => {
    const cards = buildTrainingRunCards({
      id: 4,
      run_type: "full_refresh",
      status: "success",
      started_at: "2026-05-30T13:23:00+08:00",
      finished_at: "2026-05-30T13:28:00+08:00",
      snapshot_tag: "20260530-1323",
      current_step: "finalize",
      error_step: null,
      error_message: null,
      dataset_rows: 5330,
      eligible_matches: 5981,
      complete_matches: 5330,
      coverage_ratio: "0.8912",
      last_trained_match_id: 177,
      last_trained_match_summary: "J1 Kobe 1-0 Kashima",
      last_trained_kickoff_time: "2026-05-30T18:00:00+08:00",
      new_complete_matches: null,
      artifact_paths: {}
    });

    expect(cards).toContainEqual({ label: "入训时间", value: "2026-05-30 18:00" });
  });

  it("formats run status and step labels", () => {
    expect(formatTrainingRunStatus("running")).toBe("运行中");
    expect(formatTrainingRunStatus("success")).toBe("成功");
    expect(formatTrainingRunStatus("failed")).toBe("失败");
    expect(formatTrainingRunStep("dynamic_feature_set")).toBe("动态特征");
    expect(formatTrainingRunStep("total_goals_edge_stability_v1")).toBe("大小球稳定性");
    expect(formatTrainingRunStep("total_goals_bucket_sandbox_v2")).toBe("大小球分桶沙盒");
  });
});
