import type {
  CreateFilteredPaperAutomationTasksResult,
  PaperAutomationTask
} from "./types";

export function formatFilteredAutomationResult(
  result: CreateFilteredPaperAutomationTasksResult
): string {
  const parts = [
    `创建 ${result.created_count} 个任务`,
    `已有任务跳过 ${result.skipped_existing_count} 个`,
    `已过 T-9 跳过 ${result.skipped_expired_count} 个`
  ];
  if (result.excluded_match_count > 0) {
    parts.push(`黑名单排除 ${result.excluded_match_count} 场`);
  }
  return `筛选 ${result.matched_match_count} 场比赛、${result.time_slot_count} 个时间段：${parts.join("，")}`;
}

export function mergePaperAutomationTasks(
  current: PaperAutomationTask[],
  created: PaperAutomationTask[]
): PaperAutomationTask[] {
  const createdIds = new Set(created.map((task) => task.id));
  return [...created, ...current.filter((task) => !createdIds.has(task.id))];
}
