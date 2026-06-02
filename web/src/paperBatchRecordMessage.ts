import type { PaperBatchRecordResult } from "./types";

export function formatPaperBatchRecordMessage(result: PaperBatchRecordResult): string {
  if (result.skipped_count > 0) {
    return `已记录 ${result.created_count} 条纸面观察，跳过 ${result.skipped_count} 条`;
  }
  return `已记录 ${result.created_count} 条纸面观察`;
}

export function formatPaperSingleRecordMessage(result: PaperBatchRecordResult): string {
  if (result.created_count > 0) {
    return "已记录纸面观察";
  }
  const reason = result.skipped[0]?.reason;
  return `已跳过：${formatPaperSkipReason(reason)}`;
}

function formatPaperSkipReason(reason: string | undefined): string {
  if (reason === "duplicate active paper recommendation record") {
    return "该纸面观察已记录";
  }
  return reason ?? "未创建新记录";
}
