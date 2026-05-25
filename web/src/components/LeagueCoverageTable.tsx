import type { LeagueCoverage } from "../types";

type LeagueCoverageTableProps = {
  leagues: LeagueCoverage[];
};

export function LeagueCoverageTable({ leagues }: LeagueCoverageTableProps) {
  if (leagues.length === 0) {
    return <div className="empty-state">暂无联赛覆盖率数据</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>联赛</th>
          <th>赛季</th>
          <th>完赛</th>
          <th>有赔率</th>
          <th>覆盖率</th>
          <th>未匹配</th>
        </tr>
      </thead>
      <tbody>
        {leagues.map((league) => (
          <tr key={`${league.league_id}-${league.season}`}>
            <td>{league.league_name}</td>
            <td>{league.season}</td>
            <td>{league.finished_matches}</td>
            <td>{league.matches_with_historical_odds}</td>
            <td>{(Number(league.coverage_ratio) * 100).toFixed(1)}%</td>
            <td>{league.unmatched_matches}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
