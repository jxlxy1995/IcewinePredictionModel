import type { ModelTrainingOverview, ModelTrainingRun, ModelTrainingStatus } from "./types";

export type ModelTrainingSummaryCard = {
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
    { label: "可出结果", value: readyCount.toLocaleString() }
  ];
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
