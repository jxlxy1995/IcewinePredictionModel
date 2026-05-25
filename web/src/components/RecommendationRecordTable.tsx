import type { RecommendationRecord } from "../types";

type RecommendationRecordTableProps = {
  records: RecommendationRecord[];
};

export function RecommendationRecordTable({ records }: RecommendationRecordTableProps) {
  if (records.length === 0) {
    return <div className="empty-state">暂无推荐记录</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>比赛</th>
          <th>盘口</th>
          <th>赔率</th>
          <th>信心</th>
          <th>手数</th>
          <th>状态</th>
          <th>收益</th>
        </tr>
      </thead>
      <tbody>
        {records.map((record) => (
          <tr key={record.id}>
            <td>
              {record.league_display_name ?? record.league_name}{" "}
              {record.home_team_display_name ?? record.home_team_name} vs{" "}
              {record.away_team_display_name ?? record.away_team_name}
            </td>
            <td>
              {formatMarket(record.market_type)} {record.market_line} {formatSide(record.side)}
            </td>
            <td>{record.odds}</td>
            <td>{record.confidence_grade}</td>
            <td>{record.stake_units}</td>
            <td>{formatStatus(record.status)}</td>
            <td>{record.profit_units ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatMarket(value: string) {
  if (value === "asian_handicap") {
    return "亚盘";
  }
  if (value === "total_goals") {
    return "大小球";
  }
  return value;
}

function formatSide(value: string) {
  const labels: Record<string, string> = {
    home: "主队",
    away: "客队",
    over: "大",
    under: "小"
  };
  return labels[value] ?? value;
}

function formatStatus(value: string) {
  const labels: Record<string, string> = {
    pending: "待复盘",
    settled: "已复盘"
  };
  return labels[value] ?? value;
}
