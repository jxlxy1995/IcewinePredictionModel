import type { CreatePaperAutomationTaskPayload } from "./types";

const DEFAULT_MATCH_WINDOW_OFFSET_MINUTES = 9;

export function updateDraftFromTriggerTime(
  draft: CreatePaperAutomationTaskPayload,
  triggerAt: string
): CreatePaperAutomationTaskPayload {
  const matchWindowTime = matchWindowTimeFromTrigger(triggerAt);
  return {
    ...draft,
    trigger_at: triggerAt,
    match_window_start: matchWindowTime,
    match_window_end: matchWindowTime
  };
}

function matchWindowTimeFromTrigger(triggerAt: string): string {
  if (!triggerAt) {
    return "";
  }
  const triggerDate = new Date(triggerAt);
  if (Number.isNaN(triggerDate.getTime())) {
    return "";
  }
  triggerDate.setMinutes(triggerDate.getMinutes() + DEFAULT_MATCH_WINDOW_OFFSET_MINUTES);
  return formatDateTimeLocal(triggerDate);
}

function formatDateTimeLocal(value: Date): string {
  const year = value.getFullYear();
  const month = pad2(value.getMonth() + 1);
  const day = pad2(value.getDate());
  const hours = pad2(value.getHours());
  const minutes = pad2(value.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}
