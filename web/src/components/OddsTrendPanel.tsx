import { useState } from "react";

import type { MatchOddsTrends, OddsPoint } from "../types";
import type { OddsChartPoint } from "../oddsTrendChart";
import { buildOddsChartSeries, summarizeOddsTrendAvailability } from "../oddsTrendChart";

type OddsTrendPanelProps = {
  compactHeader?: boolean;
  trends: MatchOddsTrends;
};

export function OddsTrendPanel({ compactHeader = false, trends }: OddsTrendPanelProps) {
  const availability = summarizeOddsTrendAvailability(trends);
  return (
    <>
      {!compactHeader && (
        <div className="match-heading">
          <strong>
            {trends.league_display_name ?? trends.league_name}：
            {trends.home_team_display_name ?? trends.home_team_name} vs{" "}
            {trends.away_team_display_name ?? trends.away_team_name}
          </strong>
          <span>{formatKickoff(trends.kickoff_time)}</span>
        </div>
      )}
      {!availability.hasAnyOdds && <div className="empty-state">暂无赔率走势数据</div>}
      <Trend
        title="亚盘"
        points={trends.asian_handicap}
        specs={[
          { key: "home_odds", label: "主队", color: "#2563eb" },
          { key: "away_odds", label: "客队", color: "#f97316" }
        ]}
      />
      <Trend
        title="大小球"
        points={trends.total_goals}
        specs={[
          { key: "over_odds", label: "大球", color: "#16a34a" },
          { key: "under_odds", label: "小球", color: "#dc2626" }
        ]}
      />
      <Trend
        title="胜平负"
        points={trends.match_winner}
        specs={[
          { key: "home_odds", label: "主胜", color: "#2563eb" },
          { key: "draw_odds", label: "平局", color: "#7c3aed" },
          { key: "away_odds", label: "客胜", color: "#f97316" }
        ]}
      />
    </>
  );
}

function Trend({
  title,
  points,
  specs
}: {
  title: string;
  points: OddsPoint[];
  specs: Array<{ key: keyof OddsPoint; label: string; color: string }>;
}) {
  const [activePoint, setActivePoint] = useState<OddsChartPoint | null>(null);
  const chart = buildOddsChartSeries(points, specs);
  if (!chart.hasData) {
    return <div className="empty-state">{title}暂无走势数据</div>;
  }
  const tooltipX = activePoint ? Math.min(activePoint.x + 12, 250) : 0;
  const tooltipY = activePoint ? Math.max(28, Math.min(118, minPointY(activePoint) - 14)) : 0;

  return (
    <div className="trend">
      <div className="trend-title">
        <span>{title}</span>
        <div className="trend-legend">
          {chart.series.map((line) => (
            <span key={line.key}>
              <i style={{ backgroundColor: line.color }} />
              {line.label}
              {line.latest ? ` ${line.latest}` : ""}
            </span>
          ))}
        </div>
      </div>
      <svg
        aria-label={`${title}赔率走势图`}
        className="trend-chart"
        onMouseLeave={() => setActivePoint(null)}
        onMouseMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - box.left) / box.width) * 380;
          setActivePoint(nearestPoint(chart.points, x));
        }}
        viewBox="0 0 380 192"
      >
        {chart.yTicks.map((tick) => (
          <g className="trend-grid" key={`${title}-${tick.label}`}>
            <line x1="24" x2="356" y1={tick.y} y2={tick.y} />
            <text x="18" y={tick.y + 4}>
              {tick.label}
            </text>
          </g>
        ))}
        <line className="trend-axis" x1="24" x2="356" y1="160" y2="160" />
        <line className="trend-axis" x1="24" x2="24" y1="24" y2="160" />
        {chart.series.map((line) => (
          <path d={line.path} key={line.key} stroke={line.color} />
        ))}
        {activePoint && (
          <g className="trend-hover">
            <line x1={activePoint.x} x2={activePoint.x} y1="24" y2="160" />
            {activePoint.values.map((value) => (
              <circle
                cx={activePoint.x}
                cy={value.y}
                fill={value.color}
                key={`${activePoint.index}-${value.key}`}
                r="3.5"
              />
            ))}
            <g transform={`translate(${tooltipX} ${tooltipY})`}>
              <rect height={tooltipHeight(activePoint)} rx="6" width="116" />
              <text className="trend-tooltip-title" x="8" y="16">
                {activePoint.label} · {activePoint.lineLabel}
              </text>
              {activePoint.values.map((value, index) => (
                <text key={`${value.key}-tooltip`} x="8" y={34 + index * 16}>
                  {value.label} {value.value}
                </text>
              ))}
            </g>
          </g>
        )}
        {chart.xLabels.map((label, index) =>
          index % chart.xLabelEvery === 0 || index === chart.xLabels.length - 1 ? (
            <text key={`${label}-${index}`} x={xLabelPosition(index, chart.xLabels.length)} y="184">
              {label}
            </text>
          ) : null
        )}
        {chart.lineLabels.map((label, index) =>
          index % chart.xLabelEvery === 0 || index === chart.lineLabels.length - 1 ? (
            <text
              className="trend-line-label"
              key={`${label}-${index}`}
              x={xLabelPosition(index, chart.lineLabels.length)}
              y="14"
            >
              {label}
            </text>
          ) : null
        )}
      </svg>
    </div>
  );
}

function formatKickoff(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function xLabelPosition(index: number, count: number) {
  if (count <= 1) {
    return 190;
  }
  return 24 + ((356 - 24) * index) / (count - 1);
}

function nearestPoint(points: OddsChartPoint[], x: number) {
  return points.reduce((nearest, point) =>
    Math.abs(point.x - x) < Math.abs(nearest.x - x) ? point : nearest
  );
}

function minPointY(point: OddsChartPoint) {
  return Math.min(...point.values.map((value) => value.y));
}

function tooltipHeight(point: OddsChartPoint) {
  return 28 + point.values.length * 16;
}
