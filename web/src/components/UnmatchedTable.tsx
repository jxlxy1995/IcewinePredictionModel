import type { UnmatchedMatch } from "../types";

type UnmatchedTableProps = {
  matches: UnmatchedMatch[];
};

export function UnmatchedTable({ matches }: UnmatchedTableProps) {
  if (matches.length === 0) {
    return <div className="empty-state">暂无未匹配比赛</div>;
  }
  return (
    <div className="unmatched-list">
      {matches.map((item) => (
        <div className="unmatched" key={item.match_id}>
          <strong>{item.league_name}</strong>
          <span>
            {item.home_team_name} vs {item.away_team_name}
          </span>
          <small>{item.match_reason}</small>
        </div>
      ))}
    </div>
  );
}
