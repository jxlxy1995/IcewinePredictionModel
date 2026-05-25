import type { LeagueCoverage } from "../types";

type LeagueCoverageTableProps = {
  leagues: LeagueCoverage[];
  filterText?: string;
  sortBy?: "coverage_desc" | "coverage_asc" | "unmatched_desc";
};

export function LeagueCoverageTable({
  leagues,
  filterText = "",
  sortBy = "coverage_desc"
}: LeagueCoverageTableProps) {
  const normalizedFilterText = filterText.trim().toLowerCase();
  const visibleLeagues = leagues
    .filter((league) => {
      if (!normalizedFilterText) {
        return true;
      }
      return `${league.league_name} ${league.country_or_region} ${league.season}`
        .toLowerCase()
        .includes(normalizedFilterText);
    })
    .sort((left, right) => {
      if (sortBy === "coverage_asc") {
        return Number(left.coverage_ratio) - Number(right.coverage_ratio);
      }
      if (sortBy === "unmatched_desc") {
        return right.unmatched_matches - left.unmatched_matches;
      }
      return Number(right.coverage_ratio) - Number(left.coverage_ratio);
    });

  if (visibleLeagues.length === 0) {
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
        {visibleLeagues.map((league) => (
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
