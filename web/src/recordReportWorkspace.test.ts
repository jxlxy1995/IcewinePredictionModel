import { describe, expect, it } from "vitest";

import type { RecommendationRecord } from "./types";
import {
  buildRecommendationRecordGroups,
  buildRecommendationRecordSummary,
  formatSettlementResult
} from "./recordReportWorkspace";

const records: RecommendationRecord[] = [
  {
    id: 1,
    match_id: 101,
    league_name: "Premier League",
    league_display_name: "英超",
    home_team_name: "Arsenal",
    away_team_name: "Chelsea",
    kickoff_time: "2026-05-01T22:00:00+08:00",
    market_type: "asian_handicap",
    side: "home",
    market_line: "-0.25",
    odds: "1.930",
    confidence_grade: "A",
    stake_units: "2.00",
    status: "settled",
    settlement_result: "win",
    profit_units: "1.860"
  },
  {
    id: 2,
    match_id: 102,
    league_name: "Premier League",
    league_display_name: "英超",
    home_team_name: "Wolves",
    away_team_name: "Leeds",
    kickoff_time: "2026-05-02T22:00:00+08:00",
    market_type: "total_goals",
    side: "under",
    market_line: "2.50",
    odds: "1.910",
    confidence_grade: "B+",
    stake_units: "1.00",
    status: "settled",
    settlement_result: "loss",
    profit_units: "-1.000"
  },
  {
    id: 3,
    match_id: 103,
    league_name: "Bundesliga",
    league_display_name: "德甲",
    home_team_name: "Bayern Munich",
    away_team_name: "Dortmund",
    kickoff_time: "2026-05-03T21:30:00+08:00",
    market_type: "asian_handicap",
    side: "away",
    market_line: "+0.50",
    odds: "1.880",
    confidence_grade: "B+",
    stake_units: "1.50",
    status: "settled",
    settlement_result: "half_win",
    profit_units: "0.660"
  },
  {
    id: 4,
    match_id: 104,
    league_name: "Serie A",
    league_display_name: "意甲",
    home_team_name: "Roma",
    away_team_name: "Lazio",
    kickoff_time: "2026-05-04T02:45:00+08:00",
    market_type: "total_goals",
    side: "over",
    market_line: "2.75",
    odds: "1.910",
    confidence_grade: "A-",
    stake_units: "1.00",
    status: "pending",
    settlement_result: null,
    profit_units: null
  }
];

describe("record report workspace helpers", () => {
  it("summarizes settled recommendation performance", () => {
    expect(buildRecommendationRecordSummary(records)).toEqual({
      hitRate: "66.67%",
      pendingRecords: 1,
      roi: "33.78%",
      settledRecords: 3,
      totalProfitUnits: "1.520",
      totalRecords: 4,
      totalStakeUnits: "4.50"
    });
  });

  it("groups settled records by market type, confidence grade, and league", () => {
    expect(buildRecommendationRecordGroups(records).byMarketType).toEqual([
      {
        groupName: "亚盘",
        hitRate: "100.00%",
        profitUnits: "2.520",
        recordCount: 2,
        roi: "72.00%",
        stakeUnits: "3.50"
      },
      {
        groupName: "大小球",
        hitRate: "0.00%",
        profitUnits: "-1.000",
        recordCount: 1,
        roi: "-100.00%",
        stakeUnits: "1.00"
      }
    ]);

    expect(buildRecommendationRecordGroups(records).byConfidenceGrade[0]).toMatchObject({
      groupName: "A",
      roi: "93.00%"
    });
    expect(buildRecommendationRecordGroups(records).byLeague[0]).toMatchObject({
      groupName: "英超",
      recordCount: 2,
      roi: "28.67%"
    });
  });

  it("formats settlement result labels", () => {
    expect(formatSettlementResult("win")).toBe("赢");
    expect(formatSettlementResult("half_win")).toBe("赢半");
    expect(formatSettlementResult("push")).toBe("走水");
    expect(formatSettlementResult(null)).toBe("-");
  });
});
