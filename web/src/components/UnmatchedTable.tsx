import { useState } from "react";

import type { UnmatchedMatch } from "../types";

type UnmatchedTableProps = {
  matches: UnmatchedMatch[];
};

type LocalDecision = "pending" | "confirmed" | "ignored";

export function UnmatchedTable({ matches }: UnmatchedTableProps) {
  const [decisions, setDecisions] = useState<Record<number, LocalDecision>>({});

  if (matches.length === 0) {
    return <div className="empty-state">暂无未匹配比赛</div>;
  }
  return (
    <div className="unmatched-list">
      {matches.map((item) => {
        const decision = decisions[item.match_id] ?? "pending";
        return (
          <div className={`unmatched ${decision}`} key={item.match_id}>
            <div className="unmatched-main">
              <strong>{item.league_name}</strong>
              <span>
                {item.home_team_name} vs {item.away_team_name}
              </span>
              <small>{item.match_reason}</small>
            </div>
            <div className="alias-candidates">
              {(item.alias_candidates ?? ["暂无候选"]).map((candidate) => (
                <button key={candidate} type="button">
                  {candidate}
                </button>
              ))}
            </div>
            <div className="inline-actions">
              <button onClick={() => setDecisions({ ...decisions, [item.match_id]: "confirmed" })} type="button">
                标记已确认
              </button>
              <button onClick={() => setDecisions({ ...decisions, [item.match_id]: "ignored" })} type="button">
                暂时忽略
              </button>
              <span>{formatDecision(decision)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatDecision(decision: LocalDecision) {
  if (decision === "confirmed") {
    return "本地已确认";
  }
  if (decision === "ignored") {
    return "本地已忽略";
  }
  return "待处理";
}
