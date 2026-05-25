import type { MatchOddsTrends, OddsPoint } from "../types";

type OddsTrendPanelProps = {
  trends: MatchOddsTrends;
};

export function OddsTrendPanel({ trends }: OddsTrendPanelProps) {
  return (
    <>
      <div className="match-heading">
        <strong>
          {trends.league_name}：{trends.home_team_name} vs {trends.away_team_name}
        </strong>
        <span>{formatKickoff(trends.kickoff_time)}</span>
      </div>
      <Trend title="亚盘" points={trends.asian_handicap} firstKey="home_odds" secondKey="away_odds" />
      <Trend title="大小球" points={trends.total_goals} firstKey="over_odds" secondKey="under_odds" />
    </>
  );
}

function Trend({
  title,
  points,
  firstKey,
  secondKey
}: {
  title: string;
  points: OddsPoint[];
  firstKey: keyof OddsPoint;
  secondKey: keyof OddsPoint;
}) {
  if (points.length === 0) {
    return <div className="empty-state">{title}暂无走势数据</div>;
  }
  return (
    <div className="trend">
      <div className="trend-title">{title}</div>
      <div className="trend-bars">
        {points.map((point) => (
          <div className="trend-point" key={`${title}-${point.snapshot_time}-${point.market_line}`}>
            <span>{formatSnapshotTime(point.snapshot_time)}</span>
            <div className="bar-stack">
              <i style={{ height: `${Number(point[firstKey] ?? 1.8) * 38}px` }} />
              <b style={{ height: `${Number(point[secondKey] ?? 1.8) * 38}px` }} />
            </div>
            <em>{point.market_line}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatKickoff(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function formatSnapshotTime(value: string) {
  if (!value.includes("T")) {
    return value;
  }
  return value.slice(11, 16);
}
