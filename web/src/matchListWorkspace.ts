import type { MatchDetail, MatchListMatch, MatchListWorkspace } from "./types";

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
  oddsText: string;
  scoreText: string;
  statusText: string;
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
    oddsAvailability: formatOddsAvailability(match.has_odds),
    oddsText:
      match.odds_summary.asian_handicap ??
      match.odds_summary.total_goals ??
      match.odds_summary.match_winner ??
      "-",
    scoreText: formatScore(match),
    statusText: formatMatchStatus(match.status_group)
  }));
}

export function summarizeMatchDetail(detail: MatchDetail) {
  return {
    fixture: `${detail.home_team_display_name ?? detail.home_team_name} vs ${
      detail.away_team_display_name ?? detail.away_team_name
    }`,
    recommendations: `${detail.paper_recommendation_summary.label} / ${detail.formal_recommendation_summary.label}`,
    teamData: detail.team_data_note
  };
}

export function matchTimePresetLabel(value: string): string {
  const labels: Record<string, string> = {
    all: "全部",
    next_24h: "未来 24h",
    next_3d: "未来 3 天",
    previous_24h: "过去 24h",
    previous_7d: "过去 7 天"
  };
  return labels[value] ?? value;
}

export function formatMatchStatus(value: string): string {
  const labels: Record<string, string> = {
    finished: "已完赛",
    live: "进行中",
    not_started: "未开赛"
  };
  return labels[value] ?? value;
}

export function formatOddsAvailability(hasOdds: boolean): string {
  return hasOdds ? "有赔率" : "无赔率";
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
