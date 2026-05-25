import type { MissingTeamDisplayName } from "../types";

type MissingTeamDisplayNameTableProps = {
  items: MissingTeamDisplayName[];
};

export function MissingTeamDisplayNameTable({ items }: MissingTeamDisplayNameTableProps) {
  if (items.length === 0) {
    return <div className="empty-state">暂无缺失中文名的球队</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>球队</th>
          <th>联赛</th>
          <th>赛季</th>
          <th>出现</th>
          <th>最近比赛</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={`${item.league_id}-${item.season ?? "unknown"}-${item.team_id}`}>
            <td>
              <div className="team-cell">
                {item.team_logo_url && <img alt="" src={item.team_logo_url} />}
                <span>{item.team_name}</span>
              </div>
            </td>
            <td>{item.league_display_name ?? item.league_name}</td>
            <td>{item.season ?? "-"}</td>
            <td>{item.match_count}</td>
            <td>{formatShortDateTime(item.latest_kickoff_time)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatShortDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 16);
}
