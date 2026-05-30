import type { OddsPoint } from "./types";

export type OddsSeriesSpec = {
  key: keyof OddsPoint;
  label: string;
  color: string;
};

export type OddsChartLine = OddsSeriesSpec & {
  latest: string | null;
  path: string;
};

export type OddsChartPointValue = OddsSeriesSpec & {
  value: string;
  y: number;
};

export type OddsChartPoint = {
  index: number;
  label: string;
  lineLabel: string;
  values: OddsChartPointValue[];
  x: number;
};

export type OddsChartTick = {
  label: string;
  y: number;
};

export type OddsChartSeries = {
  hasData: boolean;
  lineLabels: string[];
  points: OddsChartPoint[];
  series: OddsChartLine[];
  xLabelEvery: number;
  xLabels: string[];
  yTicks: OddsChartTick[];
};

const CHART_WIDTH = 380;
const CHART_HEIGHT = 160;
const PADDING_X = 24;
const PADDING_TOP = 24;
const PADDING_BOTTOM = 24;

export function buildOddsChartSeries(
  points: OddsPoint[],
  specs: OddsSeriesSpec[]
): OddsChartSeries {
  const usablePoints = points.filter((point) =>
    specs.some((spec) => parseOddsValue(point[spec.key]) != null)
  );
  const values = usablePoints.flatMap((point) =>
    specs
      .map((spec) => parseOddsValue(point[spec.key]))
      .filter((value): value is number => value != null)
  );

  if (usablePoints.length === 0 || values.length === 0) {
    return {
      hasData: false,
      lineLabels: [],
      points: [],
      series: specs.map((spec) => ({ ...spec, latest: null, path: "" })),
      xLabelEvery: 1,
      xLabels: [],
      yTicks: []
    };
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const domainPadding = Math.max((maxValue - minValue) * 0.08, 0.02);
  const domainMin = minValue - domainPadding;
  const domainMax = maxValue + domainPadding;

  return {
    hasData: true,
    lineLabels: usablePoints.map((point) => point.market_line),
    points: usablePoints.map((point, index) =>
      buildChartPoint(point, index, usablePoints.length, specs, domainMin, domainMax)
    ),
    series: specs.map((spec) => ({
      ...spec,
      latest: latestValue(usablePoints, spec.key),
      path: buildSvgPath(usablePoints, spec.key, domainMin, domainMax)
    })),
    xLabelEvery: Math.max(1, Math.ceil(usablePoints.length / 6)),
    xLabels: usablePoints.map((point) => formatSnapshotTime(point.snapshot_time)),
    yTicks: buildYTicks(domainMin, domainMax)
  };
}

export function summarizeOddsTrendAvailability(trends: {
  asian_handicap: OddsPoint[];
  total_goals: OddsPoint[];
  match_winner: OddsPoint[];
}) {
  const totalPoints =
    trends.asian_handicap.length + trends.total_goals.length + trends.match_winner.length;
  return {
    hasAnyOdds: totalPoints > 0,
    totalPoints
  };
}

export function formatSnapshotTime(value: string) {
  if (!value.includes("T")) {
    return value;
  }
  return value.slice(11, 16);
}

function buildSvgPath(
  points: OddsPoint[],
  key: keyof OddsPoint,
  domainMin: number,
  domainMax: number
) {
  let segmentIndex = 0;
  return points
    .map((point, index) => {
      const value = parseOddsValue(point[key]);
      if (value == null) {
        return null;
      }
      const command = segmentIndex === 0 ? "M" : "L";
      segmentIndex += 1;
      return `${command} ${xPosition(index, points.length).toFixed(2)} ${yPosition(
        value,
        domainMin,
        domainMax
      ).toFixed(2)}`;
    })
    .filter((part): part is string => part != null)
    .join(" ");
}

function buildChartPoint(
  point: OddsPoint,
  index: number,
  count: number,
  specs: OddsSeriesSpec[],
  domainMin: number,
  domainMax: number
): OddsChartPoint {
  return {
    index,
    label: formatSnapshotTime(point.snapshot_time),
    lineLabel: point.market_line,
    values: specs.flatMap((spec) => {
      const parsed = parseOddsValue(point[spec.key]);
      const value = point[spec.key];
      if (parsed == null || typeof value !== "string") {
        return [];
      }
      return [
        {
          ...spec,
          value,
          y: roundChartNumber(yPosition(parsed, domainMin, domainMax))
        }
      ];
    }),
    x: roundChartNumber(xPosition(index, count))
  };
}

function buildYTicks(domainMin: number, domainMax: number): OddsChartTick[] {
  return [domainMax, domainMin + ((domainMax - domainMin) * 2) / 3, domainMin + (domainMax - domainMin) / 3, domainMin].map(
    (value) => ({
      label: value.toFixed(2),
      y: roundChartNumber(yPosition(value, domainMin, domainMax))
    })
  );
}

function latestValue(points: OddsPoint[], key: keyof OddsPoint) {
  for (const point of [...points].reverse()) {
    const value = point[key];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

function roundChartNumber(value: number) {
  return Number(value.toFixed(2));
}

function parseOddsValue(value: OddsPoint[keyof OddsPoint]) {
  if (typeof value !== "string") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function xPosition(index: number, count: number) {
  if (count <= 1) {
    return CHART_WIDTH / 2;
  }
  return PADDING_X + ((CHART_WIDTH - PADDING_X * 2) * index) / (count - 1);
}

function yPosition(value: number, domainMin: number, domainMax: number) {
  const plotHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const ratio = (value - domainMin) / (domainMax - domainMin || 1);
  return PADDING_TOP + (1 - ratio) * plotHeight;
}
