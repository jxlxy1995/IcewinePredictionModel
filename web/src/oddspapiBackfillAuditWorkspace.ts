import type { OddspapiBackfillAudit, OddspapiLeagueBackfillAudit } from "./types";

export type OddspapiAuditSummaryCard = {
  label: string;
  value: string;
};

export type OddspapiLeagueAuditRow = OddspapiLeagueBackfillAudit & {
  issue_count: number;
  snapshot_coverage_ratio: string;
  status_summary: string;
  top_error: string;
};

const issueStatuses = new Set(["failed", "unmatched", "empty", "unavailable"]);

const statusLabels: Record<string, string> = {
  empty: "无赔率",
  failed: "失败",
  success: "成功",
  unavailable: "不可用",
  unmatched: "匹配失败",
  unknown: "未知"
};

export function buildOddspapiAuditSummaryCards(
  audit: OddspapiBackfillAudit
): OddspapiAuditSummaryCard[] {
  const worker = audit.worker_progress;
  return [
    {
      label: "当前联赛",
      value:
        worker?.current_league_display_name ||
        worker?.current_league_name ||
        "-"
    },
    {
      label: "已处理比赛",
      value: formatNumber(
        worker?.total_processed_matches ?? sumLeagueMatches(audit, "finished_matches")
      )
    },
    {
      label: "赔率快照",
      value: formatNumber(
        worker?.total_inserted_snapshots ?? sumLeagueMatches(audit, "snapshot_count")
      )
    },
    {
      label: "失败比赛",
      value: formatNumber(worker?.total_failed_matches ?? sumIssueMatches(audit))
    }
  ];
}

export function listOddspapiLeagueAuditRows(
  audit: OddspapiBackfillAudit
): OddspapiLeagueAuditRow[] {
  return audit.league_summaries
    .map((league) => ({
      ...league,
      issue_count: countIssues(league),
      snapshot_coverage_ratio: formatRatio(league.snapshot_matches, league.finished_matches),
      status_summary: formatStatusCounts(league.status_counts),
      top_error: formatTopError(league.error_counts)
    }))
    .sort((left, right) => {
      if (right.issue_count !== left.issue_count) {
        return right.issue_count - left.issue_count;
      }
      return displayLeagueName(left).localeCompare(displayLeagueName(right), "zh-Hans-CN");
    });
}

export function formatOddspapiStatusLabel(status: string): string {
  return statusLabels[status] ?? status;
}

function sumLeagueMatches(
  audit: OddspapiBackfillAudit,
  key: "finished_matches" | "snapshot_count"
): number {
  return audit.league_summaries.reduce((total, league) => total + league[key], 0);
}

function sumIssueMatches(audit: OddspapiBackfillAudit): number {
  return audit.league_summaries.reduce((total, league) => total + countIssues(league), 0);
}

function countIssues(league: OddspapiLeagueBackfillAudit): number {
  return Object.entries(league.status_counts).reduce((total, [status, count]) => {
    if (!issueStatuses.has(status)) {
      return total;
    }
    return total + count;
  }, 0);
}

function formatStatusCounts(statusCounts: Record<string, number>): string {
  const entries = Object.entries(statusCounts).filter(([, count]) => count > 0);
  if (entries.length === 0) {
    return "-";
  }
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([status, count]) => `${formatOddspapiStatusLabel(status)} ${count}`)
    .join(" / ");
}

function formatTopError(errorCounts: Record<string, number>): string {
  const [reason, count] =
    Object.entries(errorCounts).sort((left, right) => right[1] - left[1])[0] ?? [];
  if (!reason) {
    return "-";
  }
  return `${reason} x${count}`;
}

function formatRatio(count: number, total: number): string {
  if (total === 0) {
    return "0.0000";
  }
  return (count / total).toFixed(4);
}

function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function displayLeagueName(league: OddspapiLeagueBackfillAudit): string {
  return league.league_display_name || league.league_name;
}
