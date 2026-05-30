import { describe, expect, it } from "vitest";

import { buildOddsChartSeries, summarizeOddsTrendAvailability } from "./oddsTrendChart";
import type { OddsPoint } from "./types";

const points: OddsPoint[] = [
  {
    snapshot_time: "2026-05-30T10:00:00+08:00",
    bookmaker: "Pinnacle",
    market_line: "-0.25",
    home_odds: "1.900",
    away_odds: "1.980"
  },
  {
    snapshot_time: "2026-05-30T11:00:00+08:00",
    bookmaker: "Pinnacle",
    market_line: "-0.50",
    home_odds: "1.820",
    away_odds: "2.060"
  }
];

describe("oddsTrendChart", () => {
  it("builds scaled line series with labels and latest values", () => {
    const series = buildOddsChartSeries(points, [
      { key: "home_odds", label: "主队", color: "#2563eb" },
      { key: "away_odds", label: "客队", color: "#f97316" }
    ]);

    expect(series.hasData).toBe(true);
    expect(series.xLabelEvery).toBe(1);
    expect(series.xLabels).toEqual(["10:00", "11:00"]);
    expect(series.lineLabels).toEqual(["-0.25", "-0.50"]);
    expect(series.yTicks).toEqual([
      { label: "2.08", y: 24 },
      { label: "1.99", y: 61.33 },
      { label: "1.89", y: 98.67 },
      { label: "1.80", y: 136 }
    ]);
    expect(series.points).toEqual([
      {
        index: 0,
        label: "10:00",
        lineLabel: "-0.25",
        x: 24,
        values: [
          { color: "#2563eb", key: "home_odds", label: "主队", value: "1.900", y: 96 },
          { color: "#f97316", key: "away_odds", label: "客队", value: "1.980", y: 64 }
        ]
      },
      {
        index: 1,
        label: "11:00",
        lineLabel: "-0.50",
        x: 356,
        values: [
          { color: "#2563eb", key: "home_odds", label: "主队", value: "1.820", y: 128 },
          { color: "#f97316", key: "away_odds", label: "客队", value: "2.060", y: 32 }
        ]
      }
    ]);
    expect(series.series).toEqual([
      {
        key: "home_odds",
        label: "主队",
        color: "#2563eb",
        latest: "1.820",
        path: "M 24.00 96.00 L 356.00 128.00"
      },
      {
        key: "away_odds",
        label: "客队",
        color: "#f97316",
        latest: "2.060",
        path: "M 24.00 64.00 L 356.00 32.00"
      }
    ]);
  });

  it("summarizes whether a trend payload contains any odds points", () => {
    expect(
      summarizeOddsTrendAvailability({
        asian_handicap: points,
        total_goals: [],
        match_winner: []
      })
    ).toEqual({ hasAnyOdds: true, totalPoints: 2 });

    expect(
      summarizeOddsTrendAvailability({
        asian_handicap: [],
        total_goals: [],
        match_winner: []
      })
    ).toEqual({ hasAnyOdds: false, totalPoints: 0 });
  });

  it("starts a line path with the first available value when early points are missing", () => {
    const series = buildOddsChartSeries(
      [
        {
          snapshot_time: "2026-05-30T10:00:00+08:00",
          bookmaker: "Pinnacle",
          market_line: "-0.25",
          home_odds: "1.900"
        },
        {
          snapshot_time: "2026-05-30T11:00:00+08:00",
          bookmaker: "Pinnacle",
          market_line: "-0.25",
          home_odds: "1.950",
          away_odds: "1.850"
        }
      ],
      [
        { key: "home_odds", label: "主队", color: "#2563eb" },
        { key: "away_odds", label: "客队", color: "#f97316" }
      ]
    );

    expect(series.series[1].path.startsWith("M ")).toBe(true);
  });
});
