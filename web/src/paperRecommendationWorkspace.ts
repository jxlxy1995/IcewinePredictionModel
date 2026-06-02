import type {
  PaperCandidate,
  PaperGroupSummary,
  PaperRecommendationWorkspace
} from "./types";
import { toDatetimeLocalValue } from "./matchListWorkspace";

export type PaperSummaryCard = {
  label: string;
  value: string;
};

export type PaperDiagnosticCard = {
  label: string;
  meta: string;
  value: string;
};

export type PaperCandidateRow = {
  edge: string;
  fixture: string;
  isRecordable: boolean;
  kickoffTime: string;
  league: string;
  recommendation: string;
  riskText: string;
  signalKey: string;
  strategyLabel: string;
  candidate: PaperCandidate;
};

export type PaperCandidateGroupRow = {
  fixture: string;
  groupKey: string;
  kickoffTime: string;
  league: string;
  main: PaperCandidateRow;
  matchId: number;
  recordableCount: number;
  recordableSignals: PaperCandidateRow[];
  signalCount: number;
  signals: PaperCandidateRow[];
};

export type PaperDisplayGroupSummary = {
  groupName: string;
  hitRate: string;
  profitUnits: string;
  recordCount: number;
  roi: string;
  settledRecords: number;
  stakeUnits: string;
};

export type PaperRecordGroups = {
  byLeague: PaperDisplayGroupSummary[];
  byLineBucket: PaperDisplayGroupSummary[];
  byManualAdjustment: PaperDisplayGroupSummary[];
  byStrategy: PaperDisplayGroupSummary[];
};

export type PaperSignalExplanation = {
  title: string;
  formula: string;
  verdict: string;
  facts: string[];
};

export function defaultPaperRecommendationDateRange(now = new Date()): {
  start_time: string;
  end_time: string;
} {
  const end = new Date(now);
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(end.getDate() - 1);
  return {
    start_time: toDatetimeLocalValue(start),
    end_time: toDatetimeLocalValue(end)
  };
}

export function buildPaperDiagnosticCards(
  workspace: PaperRecommendationWorkspace
): PaperDiagnosticCard[] {
  const diagnostics = workspace.diagnostics;
  const statusCounts = diagnostics?.status_counts ?? {};
  const edgeThreshold = diagnostics?.edge_threshold ?? "0.1000";
  const oddsIssueCount = sumStatusCounts(statusCounts, [
    "no_odds",
    "odds_status_not_ready",
    "stale_odds"
  ]);
  return [
    {
      label: "扫描比赛",
      value: formatCount(diagnostics?.total_matches ?? workspace.candidates.length),
      meta: "候选窗口内"
    },
    {
      label: "候选比赛",
      value: formatCount(diagnostics?.candidate_match_count ?? uniqueCandidateMatchCount(workspace)),
      meta: "唯一比赛"
    },
    {
      label: "候选信号",
      value: formatCount(diagnostics?.candidate_count ?? workspace.summary.candidate_count),
      meta: "可记录信号"
    },
    {
      label: "赔率不合格",
      value: formatCount(oddsIssueCount),
      meta: "无赔率/未就绪/过期"
    },
    {
      label: "未过阈值",
      value: formatCount(statusCounts.below_threshold ?? 0),
      meta: `edge < ${edgeThreshold}`
    },
    {
      label: "未出分",
      value: formatCount(statusCounts.unscored ?? 0),
      meta: "模型无结果"
    }
  ];
}

export function explainPaperCandidateSignal(
  candidate: PaperCandidate,
  edgeThreshold = "0.1000"
): PaperSignalExplanation {
  const modelProbability = candidate.model_probability ?? "-";
  const marketProbability = candidate.market_probability ?? "-";
  const edge = candidate.edge ?? "-";
  return {
    title: candidate.strategy_display_name,
    formula: `edge = 模型概率 ${modelProbability} - 市场概率 ${marketProbability} = ${edge}`,
    verdict: candidate.is_recordable
      ? `高于阈值 ${edgeThreshold}，进入纸面候选。`
      : `未达到记录条件，状态：${formatPaperCandidateStatus(candidate.status)}。`,
    facts: [
      `盘口/选择：${formatCandidateRecommendation(candidate)}`,
      `市场类型：${formatMarketType(candidate.market_type)}`,
      `风险标签：${candidate.risk_tags.length > 0 ? candidate.risk_tags.join(", ") : "-"}`
    ]
  };
}

export function buildPaperSummaryCards(
  workspace: PaperRecommendationWorkspace
): PaperSummaryCard[] {
  return [
    { label: "候选", value: workspace.summary.candidate_count.toLocaleString() },
    { label: "已记录", value: workspace.summary.total_records.toLocaleString() },
    { label: "待结算", value: workspace.summary.pending_records.toLocaleString() },
    { label: "命中率", value: formatRatioAsPercent(workspace.summary.hit_rate) },
    { label: "ROI", value: formatRatioAsPercent(workspace.summary.roi) }
  ];
}

export function buildPaperCandidateRows(
  workspace: PaperRecommendationWorkspace
): PaperCandidateRow[] {
  return workspace.candidates.map((candidate) => ({
    candidate,
    edge: candidate.edge ?? "-",
    fixture: formatFixture(candidate),
    isRecordable: candidate.is_recordable && candidate.status === "candidate",
    kickoffTime: candidate.kickoff_time,
    league: candidate.league_display_name ?? candidate.league_name,
    recommendation: formatCandidateRecommendation(candidate),
    riskText: candidate.risk_tags.length > 0 ? candidate.risk_tags.join(", ") : "-",
    signalKey: paperCandidateSignalKey(candidate),
    strategyLabel: candidate.strategy_display_name
  }));
}

export function buildPaperCandidateGroups(
  workspace: PaperRecommendationWorkspace
): PaperCandidateGroupRow[] {
  const groups = new Map<number, PaperCandidateRow[]>();
  for (const row of buildPaperCandidateRows(workspace)) {
    const current = groups.get(row.candidate.match_id);
    if (current) {
      current.push(row);
    } else {
      groups.set(row.candidate.match_id, [row]);
    }
  }

  return Array.from(groups.entries()).map(([matchId, signals]) => {
    const main = selectMainSignal(signals);
    const recordableSignals = signals.filter((signal) => signal.isRecordable);
    return {
      fixture: main.fixture,
      groupKey: String(matchId),
      kickoffTime: main.kickoffTime,
      league: main.league,
      main,
      matchId,
      recordableCount: recordableSignals.length,
      recordableSignals,
      signalCount: signals.length,
      signals
    };
  });
}

export function paperCandidateSignalKey(candidate: PaperCandidate): string {
  return [
    candidate.match_id,
    candidate.strategy_key,
    candidate.market_type,
    candidate.side ?? "none"
  ].join(":");
}

export function buildPaperRecordGroups(
  workspace: PaperRecommendationWorkspace
): PaperRecordGroups {
  return {
    byLeague: workspace.groups.by_league.map(displayGroup),
    byLineBucket: workspace.groups.by_line_bucket.map(displayGroup),
    byManualAdjustment: workspace.groups.by_manual_adjustment.map(displayGroup),
    byStrategy: workspace.groups.by_strategy.map(displayGroup)
  };
}

export function formatPaperRecordStatus(value: string): string {
  const labels: Record<string, string> = {
    pending: "待结算",
    settled: "已结算",
    unsettleable: "暂不可结算",
    void: "已作废"
  };
  return labels[value] ?? value;
}

export function formatPaperSettlementResult(value: string | null): string {
  const labels: Record<string, string> = {
    half_loss: "输半",
    half_win: "赢半",
    loss: "输",
    push: "走水",
    win: "赢"
  };
  return value ? labels[value] ?? value : "-";
}

function displayGroup(group: PaperGroupSummary): PaperDisplayGroupSummary {
  return {
    groupName: group.group_name,
    hitRate: formatRatioAsPercent(group.hit_rate),
    profitUnits: group.total_profit_units,
    recordCount: group.record_count,
    roi: formatRatioAsPercent(group.roi),
    settledRecords: group.settled_records,
    stakeUnits: group.total_stake_units
  };
}

function uniqueCandidateMatchCount(workspace: PaperRecommendationWorkspace): number {
  return new Set(workspace.candidates.map((candidate) => candidate.match_id)).size;
}

function sumStatusCounts(statusCounts: Record<string, number>, statuses: string[]): number {
  return statuses.reduce((total, status) => total + (statusCounts[status] ?? 0), 0);
}

function formatCount(value: number): string {
  return value.toLocaleString();
}

function formatFixture(candidate: PaperCandidate): string {
  return `${candidate.home_team_display_name ?? candidate.home_team_name} vs ${
    candidate.away_team_display_name ?? candidate.away_team_name
  }`;
}

function formatCandidateRecommendation(candidate: PaperCandidate): string {
  const handicap = candidate.recommended_handicap ?? "-";
  const odds = candidate.odds ?? "-";
  return `${handicap} @ ${odds}`;
}

function selectMainSignal(signals: PaperCandidateRow[]): PaperCandidateRow {
  return signals.reduce((best, signal) => {
    if (signal.isRecordable !== best.isRecordable) {
      return signal.isRecordable ? signal : best;
    }
    return numericEdge(signal) > numericEdge(best) ? signal : best;
  });
}

function numericEdge(row: PaperCandidateRow): number {
  const value = Number(row.candidate.edge);
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function formatRatioAsPercent(value: string): string {
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatMarketType(value: string): string {
  const labels: Record<string, string> = {
    asian_handicap: "亚盘",
    match_winner: "胜平负",
    total_goals: "大小球"
  };
  return labels[value] ?? value;
}

function formatPaperCandidateStatus(value: string): string {
  const labels: Record<string, string> = {
    already_recorded: "已记录",
    below_threshold: "未过阈值",
    candidate: "候选",
    no_odds: "无赔率",
    odds_status_not_ready: "赔率状态不合格",
    stale_odds: "赔率过期",
    unscored: "模型未出分"
  };
  return labels[value] ?? value;
}
