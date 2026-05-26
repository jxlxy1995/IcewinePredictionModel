import type { RecommendationRecord } from "./types";

export type RecommendationRecordSummary = {
  hitRate: string;
  pendingRecords: number;
  roi: string;
  settledRecords: number;
  totalProfitUnits: string;
  totalRecords: number;
  totalStakeUnits: string;
};

export type RecommendationRecordGroupSummary = {
  groupName: string;
  hitRate: string;
  profitUnits: string;
  recordCount: number;
  roi: string;
  stakeUnits: string;
};

export type RecommendationRecordGroups = {
  byConfidenceGrade: RecommendationRecordGroupSummary[];
  byLeague: RecommendationRecordGroupSummary[];
  byMarketType: RecommendationRecordGroupSummary[];
};

const HIT_RESULTS = new Set(["win", "half_win"]);

export function buildRecommendationRecordSummary(
  records: RecommendationRecord[]
): RecommendationRecordSummary {
  const settledRecords = records.filter(isSettledRecord);
  const totalStakeUnits = sumNumbers(settledRecords.map((record) => record.stake_units));
  const totalProfitUnits = sumNumbers(
    settledRecords.map((record) => record.profit_units ?? "0")
  );
  return {
    hitRate: formatPercentage(hitCount(settledRecords), settledRecords.length),
    pendingRecords: records.filter((record) => record.status !== "settled").length,
    roi: formatPercentage(totalProfitUnits, totalStakeUnits),
    settledRecords: settledRecords.length,
    totalProfitUnits: totalProfitUnits.toFixed(3),
    totalRecords: records.length,
    totalStakeUnits: totalStakeUnits.toFixed(2)
  };
}

export function buildRecommendationRecordGroups(
  records: RecommendationRecord[]
): RecommendationRecordGroups {
  const settledRecords = records.filter(isSettledRecord);
  return {
    byConfidenceGrade: buildGroups(settledRecords, (record) => record.confidence_grade),
    byLeague: buildGroups(
      settledRecords,
      (record) => record.league_display_name ?? record.league_name
    ),
    byMarketType: buildGroups(settledRecords, (record) => formatMarketType(record.market_type))
  };
}

export function formatSettlementResult(value: string | null): string {
  const labels: Record<string, string> = {
    half_loss: "输半",
    half_win: "赢半",
    loss: "输",
    push: "走水",
    win: "赢"
  };
  return value ? labels[value] ?? value : "-";
}

function buildGroups(
  records: RecommendationRecord[],
  getGroupName: (record: RecommendationRecord) => string
): RecommendationRecordGroupSummary[] {
  const grouped = new Map<string, RecommendationRecord[]>();
  for (const record of records) {
    const groupName = getGroupName(record);
    grouped.set(groupName, [...(grouped.get(groupName) ?? []), record]);
  }
  return Array.from(grouped.entries())
    .map(([groupName, groupRecords]) => {
      const stakeUnits = sumNumbers(groupRecords.map((record) => record.stake_units));
      const profitUnits = sumNumbers(groupRecords.map((record) => record.profit_units ?? "0"));
      return {
        groupName,
        hitRate: formatPercentage(hitCount(groupRecords), groupRecords.length),
        profitUnits: profitUnits.toFixed(3),
        recordCount: groupRecords.length,
        roi: formatPercentage(profitUnits, stakeUnits),
        stakeUnits: stakeUnits.toFixed(2)
      };
    })
    .sort((left, right) => Number(right.profitUnits) - Number(left.profitUnits));
}

function isSettledRecord(record: RecommendationRecord): boolean {
  return record.status === "settled";
}

function hitCount(records: RecommendationRecord[]): number {
  return records.filter((record) => HIT_RESULTS.has(record.settlement_result ?? "")).length;
}

function sumNumbers(values: string[]): number {
  return values.reduce((total, value) => total + Number(value), 0);
}

function formatPercentage(numerator: number, denominator: number): string {
  if (denominator === 0) {
    return "0.00%";
  }
  return `${((numerator / denominator) * 100).toFixed(2)}%`;
}

function formatMarketType(value: string): string {
  const names: Record<string, string> = {
    asian_handicap: "亚盘",
    total_goals: "大小球"
  };
  return names[value] ?? value;
}
