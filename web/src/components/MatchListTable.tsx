import { CloudCog, CloudOff } from "lucide-react";

import type { MatchListMatch } from "../types";
import { buildMatchListRows } from "../matchListWorkspace";
import type { MatchListWorkspace } from "../types";

type MatchListTableProps = {
  isBusy?: boolean;
  onOpenMatch: (match: MatchListMatch) => void;
  onSyncFixturesResults?: (match: MatchListMatch) => void;
  onSyncOdds?: (match: MatchListMatch) => void;
  onSyncZqcf918Odds?: (match: MatchListMatch) => void;
  workspace: MatchListWorkspace;
};

export function MatchListTable({
  isBusy = false,
  onOpenMatch,
  onSyncFixturesResults,
  onSyncOdds,
  onSyncZqcf918Odds,
  workspace
}: MatchListTableProps) {
  const rows = buildMatchListRows(workspace);
  if (rows.length === 0) {
    return <div className="empty-state">当前筛选下暂无比赛</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>开赛</th>
          <th>联赛</th>
          <th>比赛</th>
          <th>状态</th>
          <th>比分</th>
          <th>赔率</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            className="clickable-row"
            key={row.match.match_id}
            onClick={() => onOpenMatch(row.match)}
          >
            <td>{row.kickoffTime}</td>
            <td>
              <span className="league-cell">
                {row.league}
                {row.isTheOddsApiUnsupportedLeague && (
                  <TheOddsApiUnsupportedIcon hasZqcf918MatchId={row.hasZqcf918MatchId} />
                )}
              </span>
            </td>
            <td>
              <TeamName
                logoUrl={row.match.home_team_logo_url}
                name={row.match.home_team_display_name ?? row.match.home_team_name}
              />
              <span className="versus-text">vs</span>
              <TeamName
                logoUrl={row.match.away_team_logo_url}
                name={row.match.away_team_display_name ?? row.match.away_team_name}
              />
            </td>
            <td>{row.statusText}</td>
            <td>{row.scoreText}</td>
            <td>{row.oddsAvailability}</td>
            <td>
              <div className="inline-actions">
                <button
                  disabled={isBusy}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSyncFixturesResults?.(row.match);
                  }}
                  type="button"
                >
                  赛果
                </button>
                <button
                  disabled={isBusy}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSyncOdds?.(row.match);
                  }}
                  type="button"
                >
                  赔率
                </button>
                <button
                  disabled={isBusy}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSyncZqcf918Odds?.(row.match);
                  }}
                  type="button"
                >
                  财富赔率
                </button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TheOddsApiUnsupportedIcon({ hasZqcf918MatchId }: { hasZqcf918MatchId: boolean }) {
  const Icon = hasZqcf918MatchId ? CloudCog : CloudOff;
  const label = hasZqcf918MatchId
    ? "The Odds API 不支持该联赛，已配置足球财富 matchID，可使用备用赔率源"
    : "The Odds API 不支持该联赛，尚未配置足球财富 matchID";
  return (
    <span aria-label={label} title={label}>
      <Icon
        aria-hidden="true"
        className={`the-odds-api-unsupported-icon ${
          hasZqcf918MatchId ? "ready" : "missing"
        }`}
        size={14}
      />
    </span>
  );
}

function TeamName({ logoUrl, name }: { logoUrl?: string | null; name: string }) {
  return (
    <span className="team-name-cell">
      {logoUrl ? <img alt="" src={logoUrl} /> : <span className="team-logo-placeholder" />}
      {name}
    </span>
  );
}
