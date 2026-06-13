import type {
  ExecutionTimepointCoverage,
  MatchDetail,
  MatchListMatch,
  MatchListWorkspace,
  MatchSyncReport
} from "./types";

export type MatchFreshnessCard = {
  label: string;
  meta: string;
  value: string;
};

export type MatchListDisplayRow = {
  fixture: string;
  kickoffTime: string;
  league: string;
  match: MatchListMatch;
  oddsAvailability: string;
  scoreText: string;
  statusText: string;
};

export type MatchSyncSummary = {
  title: string;
  line: string;
};

export type MatchTimeFilterKey = "start_time" | "end_time";

export type MatchTimeFilterChange = {
  end_time?: string;
  league_name: string;
  start_time?: string;
};

export type ExecutionTimepointCoverageView = {
  summary: string;
  healthClassName: string;
  healthLabel: string;
  targets: string[];
  rows: {
    marketType: string;
    marketLabel: string;
    cells: {
      label: string;
      available: boolean;
      canCreateManualOdds: boolean;
      className: string;
      marketType: string;
      targetMinutes: number;
      title: string;
    }[];
  }[];
};

export function buildMatchFreshnessCards(workspace: MatchListWorkspace): MatchFreshnessCard[] {
  return [
    {
      label: "赛程/赛果同步",
      value: formatDateTime(workspace.freshness.latest_fixtures_results_sync),
      meta: "默认 3 天"
    },
    {
      label: "赔率同步",
      value: formatDateTime(workspace.freshness.latest_odds_sync),
      meta: "默认 2 天"
    },
    {
      label: "库内最新开赛",
      value: formatDateTime(workspace.freshness.latest_kickoff_time),
      meta: "辅助参考"
    },
    {
      label: "最新赔率快照",
      value: formatDateTime(workspace.freshness.latest_odds_snapshot_time),
      meta: "辅助参考"
    }
  ];
}

export function buildMatchListRows(workspace: MatchListWorkspace): MatchListDisplayRow[] {
  return workspace.matches.map((match) => ({
    fixture: `${match.home_team_display_name ?? match.home_team_name} vs ${
      match.away_team_display_name ?? match.away_team_name
    }`,
    kickoffTime: formatDateTime(match.kickoff_time),
    league: match.league_display_name ?? match.league_name,
    match,
    oddsAvailability: formatOddsAvailability(match),
    scoreText: formatScore(match),
    statusText: formatMatchStatus(match.status)
  }));
}

export function summarizeMatchDetail(detail: MatchDetail) {
  return {
    fixture: `${detail.home_team_display_name ?? detail.home_team_name} vs ${
      detail.away_team_display_name ?? detail.away_team_name
    }`,
    localMatchId: `local match_id: ${detail.match_id}`,
    recommendations: `${detail.paper_recommendation_summary.label} / ${detail.formal_recommendation_summary.label}`,
    teamData: detail.team_data_note
  };
}

export function buildExecutionTimepointCoverageView(
  coverage: ExecutionTimepointCoverage
): ExecutionTimepointCoverageView {
  return {
    summary: `${coverage.available_count}/${coverage.total_count}`,
    healthClassName: `coverage-health coverage-health-${coverage.health_key}`,
    healthLabel: coverage.health_label,
    targets: coverage.targets,
    rows: coverage.rows.map((row) => ({
      marketType: row.market_type,
      marketLabel: row.market_label,
      cells: row.cells.map((cell) => ({
        label: cell.label,
        available: cell.available,
        canCreateManualOdds: !cell.available,
        className: `coverage-cell ${cell.available ? "available" : "missing"}`,
        marketType: row.market_type,
        targetMinutes: cell.target_minutes,
        title: cell.available
          ? `${cell.label} · ${formatDateTime(cell.snapshot_time)} · 盘口 ${cell.market_line ?? "-"}`
          : `${cell.label} · 缺失`
      }))
    }))
  };
}

export function buildMatchSyncSummary(report: MatchSyncReport): MatchSyncSummary {
  if (report.sync_type === "fixtures_range") {
    return {
      title: "赛程拉取结果",
      line: `新增 ${report.created_count ?? 0} 场，更新 ${report.updated_count ?? 0} 场，跳过 ${report.skipped_count}，请求 ${report.requests_used}`
    };
  }
  return {
    title: report.sync_type === "odds" ? "赔率同步结果" : "赛程/赛果同步结果",
    line: `目标 ${report.target_count} 场，成功 ${report.success_count}，失败 ${report.failed_count}，跳过 ${report.skipped_count}，请求 ${report.requests_used}`
  };
}

export function defaultMatchListDateRange(now = new Date()): {
  start_time: string;
  end_time: string;
} {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 1);
  end.setHours(12, 0, 0, 0);
  return {
    start_time: toDatetimeLocalValue(start),
    end_time: toDatetimeLocalValue(end)
  };
}

export function buildMatchTimeFilterChange(
  key: MatchTimeFilterKey,
  value: string
): MatchTimeFilterChange {
  return {
    [key]: value,
    league_name: ""
  };
}

export function toDatetimeLocalValue(value: string | Date | null): string {
  if (!value) {
    return "";
  }
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return typeof value === "string" ? value : "";
  }
  const year = parsed.getFullYear();
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  const hour = `${parsed.getHours()}`.padStart(2, "0");
  const minute = `${parsed.getMinutes()}`.padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

export function formatMatchStatus(value: string): string {
  if (["1h", "2h", "ht"].includes(value.toLowerCase())) {
    return "待填赛果";
  }
  const labels: Record<string, string> = {
    finished: "已完赛",
    live: "进行中",
    not_started: "未开赛",
    scheduled: "未开赛",
    pending_result: "待填赛果"
  };
  return labels[value] ?? value;
}

export function formatOddsAvailability(matchOrHasOdds: MatchListMatch | boolean): string {
  if (typeof matchOrHasOdds !== "boolean") {
    return matchOrHasOdds.odds_status_label ?? (matchOrHasOdds.has_odds ? "有赔率" : "无赔率");
  }
  return matchOrHasOdds ? "有赔率" : "无赔率";
}

function formatScore(match: MatchListMatch): string {
  if (match.home_score == null || match.away_score == null) {
    return "-";
  }
  return `${match.home_score}-${match.away_score}`;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const year = parsed.getFullYear();
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  const hour = `${parsed.getHours()}`.padStart(2, "0");
  const minute = `${parsed.getMinutes()}`.padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}`;
}
