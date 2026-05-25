import { useMemo } from "react";

import type { TeamDisplayNameRow } from "../types";

type TeamDisplayNameEditorProps = {
  draftNames: Record<string, string>;
  onDraftNamesChange: (draftNames: Record<string, string>) => void;
  teams: TeamDisplayNameRow[];
};

export function TeamDisplayNameEditor({
  draftNames,
  onDraftNamesChange,
  teams
}: TeamDisplayNameEditorProps) {
  const yamlSnippet = useMemo(() => {
    const lines = Object.entries(draftNames)
      .map(([teamName, displayName]) => [teamName, displayName.trim()])
      .filter(([, displayName]) => displayName.length > 0)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([teamName, displayName]) => `  ${teamName}: ${displayName}`);
    return lines.length > 0 ? ["teams:", ...lines].join("\n") : "";
  }, [draftNames]);

  if (teams.length === 0) {
    return <div className="empty-state">暂无球队数据</div>;
  }

  return (
    <div className="editor-layout">
      <table>
        <thead>
          <tr>
            <th>排名</th>
            <th>球队</th>
            <th>当前中文名</th>
            <th>手工填写</th>
            <th>出现</th>
            <th>最近比赛</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((item) => (
            <tr key={`${item.league_id}-${item.season ?? "unknown"}-${item.team_id}`}>
              <td>{formatRank(item)}</td>
              <td>
                <div className="team-cell">
                  {item.team_logo_url && <img alt="" src={item.team_logo_url} />}
                  <span>{item.team_name}</span>
                </div>
              </td>
              <td>{item.team_display_name ?? "-"}</td>
              <td>
                <input
                  className="inline-input"
                  onChange={(event) =>
                    onDraftNamesChange({ ...draftNames, [item.team_name]: event.target.value })
                  }
                  placeholder={item.is_missing_display_name ? "输入中文名" : "可覆盖当前译名"}
                  value={draftNames[item.team_name] ?? ""}
                />
              </td>
              <td>{item.match_count}</td>
              <td>{formatShortDateTime(item.latest_kickoff_time)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="yaml-preview">
        <div className="trend-title">待写入片段</div>
        <pre>{yamlSnippet || "在上方填写中文名后生成 YAML 片段"}</pre>
      </div>
    </div>
  );
}

function formatRank(item: TeamDisplayNameRow) {
  if (!item.rank) {
    return "-";
  }
  if (item.points == null) {
    return item.rank;
  }
  return `${item.rank} / ${item.points}分`;
}

function formatShortDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 16);
}
