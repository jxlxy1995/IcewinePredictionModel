import type { PaperAutomationTask } from "./types";

export type PaperAutomationSummary = {
  pending: number;
  running: number;
  completedToday: number;
  failedOrNotificationFailed: number;
};

export function buildPaperAutomationSummary(
  tasks: PaperAutomationTask[],
  now: string | Date = new Date()
): PaperAutomationSummary {
  const todayKey = toLocalDateKey(now);
  return tasks.reduce<PaperAutomationSummary>(
    (summary, task) => {
      if (task.status === "pending") {
        summary.pending += 1;
      }
      if (task.status === "running") {
        summary.running += 1;
      }
      if (task.status === "success" && task.finished_at && toLocalDateKey(task.finished_at) === todayKey) {
        summary.completedToday += 1;
      }
      if (task.status === "failed" || task.notification_status === "failed") {
        summary.failedOrNotificationFailed += 1;
      }
      return summary;
    },
    { pending: 0, running: 0, completedToday: 0, failedOrNotificationFailed: 0 }
  );
}

export function formatAutomationStatus(status: string): string {
  const labels: Record<string, string> = {
    cancelled: "已取消",
    failed: "失败",
    missed: "已错过",
    pending: "待执行",
    running: "执行中",
    success: "成功"
  };
  return labels[status] ?? status;
}

export function formatNotificationStatus(status: string): string {
  const labels: Record<string, string> = {
    failed: "失败",
    not_configured: "未配置",
    pending: "待推送",
    sent: "已发送"
  };
  return labels[status] ?? status;
}

export function formatAutomationWindow(task: PaperAutomationTask): string {
  return `${formatShortDateTime(task.match_window_start)} - ${formatShortDateTime(task.match_window_end)}`;
}

export function formatShortDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 16);
}

function toLocalDateKey(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}
