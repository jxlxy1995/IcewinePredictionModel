import type {
  ModelTrainingOverview,
  ModelTrainingRun,
  ModelTrainingStatus,
  TrainingRun,
  TrainingRunStatus,
  TrainingWorkspace
} from "./types";

export type ModelTrainingSummaryCard = {
  label: string;
  value: string;
};

export type TrainingWorkspaceCard = {
  label: string;
  value: string;
};

export type TrainingMarketRow = {
  marketType: string;
  marketLabel: string;
  evaluatedCount: number;
  skippedCount: number;
  accuracy: string;
  logLoss: string;
  brier: string;
  flatBetRoi: string;
};

export type TrainingRunCard = {
  label: string;
  value: string;
};

export function buildModelTrainingSummaryCards(
  overview: ModelTrainingOverview
): ModelTrainingSummaryCard[] {
  const readyCount = overview.model_runs.filter((run) => run.status === "ready").length;
  return [
    { label: "训练样本", value: overview.total_training_matches.toLocaleString() },
    { label: "赔率快照", value: overview.total_training_snapshots.toLocaleString() },
    { label: "模型版本", value: overview.model_runs.length.toLocaleString() },
    { label: "可用结果", value: readyCount.toLocaleString() }
  ];
}

export function buildTrainingWorkspaceCards(
  workspace: TrainingWorkspace
): TrainingWorkspaceCard[] {
  return [
    { label: "训练集样本", value: workspace.dataset.row_count.toLocaleString() },
    { label: "数据质量问题", value: countTrainingQualityIssues(workspace).toLocaleString() },
    { label: "Thin history", value: workspace.qa.thin_history_count.toLocaleString() },
    {
      label: "市场基准样本",
      value: workspace.market_baseline.evaluated_market_samples.toLocaleString()
    }
  ];
}

export function buildTrainingRunCards(run: TrainingRun | null): TrainingRunCard[] {
  if (!run) {
    return [
      { label: "最近更新", value: "暂无" },
      { label: "训练样本", value: "0" },
      { label: "入训时间", value: "暂无" },
      { label: "最后入训", value: "暂无" }
    ];
  }
  return [
    { label: "最近更新", value: formatDateTimeCompact(run.finished_at ?? run.started_at) },
    { label: "训练样本", value: (run.dataset_rows ?? 0).toLocaleString() },
    { label: "覆盖率", value: run.coverage_ratio ?? "暂无" },
    { label: "入训时间", value: formatDateTimeCompact(run.last_trained_kickoff_time) },
    { label: "最后入训", value: run.last_trained_match_summary ?? "暂无" }
  ];
}

export function countTrainingQualityIssues(workspace: TrainingWorkspace): number {
  return (
    workspace.qa.empty_required_cells +
    workspace.qa.invalid_odds_cells +
    workspace.qa.invalid_probability_cells +
    workspace.qa.invalid_overround_cells
  );
}

export function listTrainingMarketRows(workspace: TrainingWorkspace): TrainingMarketRow[] {
  return ["asian_handicap", "total_goals", "match_winner"]
    .map((marketType) => {
      const report = workspace.market_baseline.market_reports[marketType];
      if (!report) {
        return null;
      }
      return {
        marketType,
        marketLabel: formatMarketType(marketType),
        evaluatedCount: report.evaluated_count,
        skippedCount: report.skipped_count,
        accuracy: report.accuracy,
        logLoss: report.log_loss,
        brier: report.brier,
        flatBetRoi: report.flat_bet_roi
      };
    })
    .filter((row): row is TrainingMarketRow => row !== null);
}

export function listRecentModelRuns(overview: ModelTrainingOverview): ModelTrainingRun[] {
  return [...overview.model_runs].sort(
    (left, right) =>
      new Date(right.trained_at).getTime() - new Date(left.trained_at).getTime()
  );
}

export function formatModelTrainingStatus(status: ModelTrainingStatus): string {
  const statusText: Record<ModelTrainingStatus, string> = {
    failed: "失败",
    ready: "可用",
    training: "训练中"
  };
  return statusText[status];
}

export function formatTrainingRunStatus(status: TrainingRunStatus): string {
  const statusText: Record<TrainingRunStatus, string> = {
    failed: "失败",
    running: "运行中",
    success: "成功"
  };
  return statusText[status];
}

export function formatTrainingRunStep(step: string | null): string {
  if (!step) {
    return "等待中";
  }
  const names: Record<string, string> = {
    away_cover_stability: "客队方向稳定性",
    baseline_dataset: "训练集",
    dataset_qa: "数据 QA",
    dynamic_feature_set: "动态特征",
    feature_set: "基础特征",
    finalize: "收尾",
    market_baseline: "市场基准",
    queued: "排队中"
  };
  return names[step] ?? step;
}

function formatDateTimeCompact(value: string | null): string {
  if (!value) {
    return "暂无";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const pad = (part: number) => part.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

export function formatMarketType(value: string): string {
  const names: Record<string, string> = {
    asian_handicap: "亚盘",
    match_winner: "胜平负",
    score_distribution: "比分分布",
    total_goals: "大小球"
  };
  return names[value] ?? value;
}
