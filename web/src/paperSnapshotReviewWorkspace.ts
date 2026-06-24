import { toDatetimeLocalValue } from "./matchListWorkspace";
import type { PaperSnapshotReviewGroupSummary, PaperSnapshotReviewWorkspace } from "./types";

export type PaperSnapshotReviewFilters = {
  from_date: string;
  to_date: string;
  snapshot_source: string;
};

export type PaperSnapshotReviewCard = {
  label: string;
  value: string;
};

export type PaperSnapshotReviewRow = {
  flatProfitUnits: string;
  flatRoi: string;
  groupCount: number;
  groupName: string;
  pendingGroups: number;
  settledGroups: number;
  stakeUnits: string;
  weightedProfitUnits: string;
  weightedRoi: string;
};

export type PaperSnapshotReviewPreset =
  | "all"
  | "last7"
  | "last30"
  | "last60"
  | "thisWeek"
  | "lastWeek"
  | "thisMonth"
  | "lastMonth";

export const paperSnapshotReviewPresetOptions: Array<{ key: PaperSnapshotReviewPreset; label: string }> = [
  { key: "all", label: "全部历史" },
  { key: "last7", label: "近7天" },
  { key: "last30", label: "近30天" },
  { key: "last60", label: "近60天" },
  { key: "thisWeek", label: "本周" },
  { key: "lastWeek", label: "上周" },
  { key: "thisMonth", label: "本月" },
  { key: "lastMonth", label: "上月" }
];

export function defaultPaperSnapshotReviewFilters(now = new Date()): PaperSnapshotReviewFilters {
  return {
    ...buildPaperSnapshotReviewPresetRange("all", now),
    snapshot_source: "historical_backfill"
  };
}

export function buildPaperSnapshotReviewCards(
  workspace: PaperSnapshotReviewWorkspace
): PaperSnapshotReviewCard[] {
  return [
    { label: "快照组数", value: workspace.summary.group_count.toLocaleString() },
    { label: "已结算", value: workspace.summary.settled_groups.toLocaleString() },
    { label: "Pending", value: workspace.summary.pending_groups.toLocaleString() },
    { label: "建议手数", value: workspace.summary.suggested_stake_units },
    { label: "Flat ROI", value: formatRatioAsPercent(workspace.summary.flat_roi) },
    { label: "Weighted ROI", value: formatRatioAsPercent(workspace.summary.weighted_roi) }
  ];
}

export function buildPaperSnapshotReviewRows(
  groups: PaperSnapshotReviewGroupSummary[]
): PaperSnapshotReviewRow[] {
  return groups.map((group) => ({
    flatProfitUnits: group.flat_profit_units,
    flatRoi: formatRatioAsPercent(group.flat_roi),
    groupCount: group.group_count,
    groupName: group.group_name,
    pendingGroups: group.pending_groups,
    settledGroups: group.settled_groups,
    stakeUnits: group.suggested_stake_units,
    weightedProfitUnits: group.weighted_profit_units,
    weightedRoi: formatRatioAsPercent(group.weighted_roi)
  }));
}

export function buildPaperSnapshotReviewPresetRange(
  preset: PaperSnapshotReviewPreset,
  now = new Date()
): { from_date: string; to_date: string } {
  const todayEnd = endOfDay(now);
  if (preset === "all") {
    return {
      from_date: "2026-05-01T00:00",
      to_date: toDatetimeLocalValue(todayEnd)
    };
  }
  if (preset === "last7") {
    return rangeFromDays(7, now);
  }
  if (preset === "last30") {
    return rangeFromDays(30, now);
  }
  if (preset === "last60") {
    return rangeFromDays(60, now);
  }
  if (preset === "thisMonth") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
    return { from_date: toDatetimeLocalValue(start), to_date: toDatetimeLocalValue(todayEnd) };
  }
  if (preset === "lastMonth") {
    const start = new Date(now.getFullYear(), now.getMonth() - 1, 1, 0, 0, 0, 0);
    const end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 0, 0);
    return { from_date: toDatetimeLocalValue(start), to_date: toDatetimeLocalValue(end) };
  }
  const dayOfWeek = (now.getDay() + 6) % 7;
  const thisWeekStart = startOfDay(now);
  thisWeekStart.setDate(thisWeekStart.getDate() - dayOfWeek);
  if (preset === "thisWeek") {
    return { from_date: toDatetimeLocalValue(thisWeekStart), to_date: toDatetimeLocalValue(todayEnd) };
  }
  const lastWeekStart = new Date(thisWeekStart);
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);
  const lastWeekEnd = new Date(thisWeekStart);
  lastWeekEnd.setMinutes(lastWeekEnd.getMinutes() - 1);
  return { from_date: toDatetimeLocalValue(lastWeekStart), to_date: toDatetimeLocalValue(lastWeekEnd) };
}

function rangeFromDays(days: number, now: Date): { from_date: string; to_date: string } {
  const end = endOfDay(now);
  const start = startOfDay(now);
  start.setDate(start.getDate() - days + 1);
  return { from_date: toDatetimeLocalValue(start), to_date: toDatetimeLocalValue(end) };
}

function startOfDay(value: Date): Date {
  const result = new Date(value);
  result.setHours(0, 0, 0, 0);
  return result;
}

function endOfDay(value: Date): Date {
  const result = new Date(value);
  result.setHours(23, 59, 0, 0);
  return result;
}

function formatRatioAsPercent(value: string): string {
  const numeric = Number.parseFloat(value);
  if (Number.isNaN(numeric)) {
    return "-";
  }
  return `${(numeric * 100).toFixed(2)}%`;
}
