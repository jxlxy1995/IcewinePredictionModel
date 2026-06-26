import type {
  ExecutionTimepointCoverage,
  ExecutionTimepointOddsTable,
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
  hasZqcf918MatchId: boolean;
  isTheOddsApiUnsupportedLeague: boolean;
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
  bookmaker: string | null;
  bookmakerLabel: string | null;
  canClearSbobet: boolean;
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

export type ExecutionTimepointOddsTableView = {
  rows: {
    label: string;
    asianHandicap: {
      time: string;
      line: string;
      home: string;
      away: string;
      isMissing: boolean;
    };
    totalGoals: {
      time: string;
      line: string;
      over: string;
      under: string;
      isMissing: boolean;
    };
    matchWinner: {
      time: string;
      home: string;
      draw: string;
      away: string;
      isMissing: boolean;
    };
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
    hasZqcf918MatchId: Boolean(match.zqcf918_match_id),
    isTheOddsApiUnsupportedLeague: match.the_odds_api_unsupported,
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
  const bookmaker = coverage.bookmaker?.toLowerCase() ?? null;
  const isSbobet = bookmaker === "sbobet";
  return {
    summary: `${coverage.available_count}/${coverage.total_count}`,
    healthClassName: `coverage-health coverage-health-${coverage.health_key}`,
    healthLabel: coverage.health_label,
    bookmaker,
    bookmakerLabel: formatBookmakerLabel(bookmaker),
    canClearSbobet: isSbobet,
    targets: coverage.targets,
    rows: coverage.rows.map((row) => ({
      marketType: row.market_type,
      marketLabel: row.market_label,
      cells: row.cells.map((cell) => ({
        label: cell.label,
        available: cell.available,
        canCreateManualOdds: !cell.available && !isSbobet,
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

export function buildExecutionTimepointOddsTableView(
  table: ExecutionTimepointOddsTable
): ExecutionTimepointOddsTableView {
  return {
    rows: table.rows.map((row) => ({
      label: row.label,
      asianHandicap: {
        time: formatCompactDateTime(row.asian_handicap.snapshot_time),
        line: row.asian_handicap.market_line ?? "-",
        home: row.asian_handicap.home_odds ?? "-",
        away: row.asian_handicap.away_odds ?? "-",
        isMissing: row.asian_handicap.snapshot_time == null
      },
      totalGoals: {
        time: formatCompactDateTime(row.total_goals.snapshot_time),
        line: row.total_goals.market_line ?? "-",
        over: row.total_goals.over_odds ?? "-",
        under: row.total_goals.under_odds ?? "-",
        isMissing: row.total_goals.snapshot_time == null
      },
      matchWinner: {
        time: formatCompactDateTime(row.match_winner.snapshot_time),
        home: row.match_winner.home_odds ?? "-",
        draw: row.match_winner.draw_odds ?? "-",
        away: row.match_winner.away_odds ?? "-",
        isMissing: row.match_winner.snapshot_time == null
      }
    }))
  };
}

function formatBookmakerLabel(bookmaker: string | null): string | null {
  if (bookmaker === "pinnacle") {
    return "Pinnacle";
  }
  if (bookmaker === "sbobet") {
    return "SBOBet";
  }
  return null;
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

function formatCompactDateTime(value: string | null): string {
  const formatted = formatDateTime(value);
  if (formatted === "-") {
    return "-";
  }
  return formatted.slice(5);
}
