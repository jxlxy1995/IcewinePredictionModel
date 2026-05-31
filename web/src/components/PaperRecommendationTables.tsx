import { useState } from "react";

import type { PaperCandidate, PaperRecord } from "../types";
import {
  buildPaperCandidateRows,
  formatPaperRecordStatus,
  formatPaperSettlementResult
} from "../paperRecommendationWorkspace";
import type { PaperRecommendationWorkspace } from "../types";
import {
  MatchCell,
  ProfitCell,
  RecordPagination,
  SettlementBadge,
  useSortedPaginatedRecords
} from "./RecommendationRecordDisplay";

type PaperCandidateTableProps = {
  isBusy: boolean;
  onRecord: (candidate: PaperCandidate) => void;
  workspace: PaperRecommendationWorkspace;
};

type PaperRecordTableProps = {
  isBusy: boolean;
  onEdit: (
    record: PaperRecord,
    payload: { current_market_line: string; current_odds: string; manual_note: string }
  ) => void;
  onVoid: (record: PaperRecord) => void;
  records: PaperRecord[];
};

export function PaperCandidateTable({
  isBusy,
  onRecord,
  workspace
}: PaperCandidateTableProps) {
  const rows = buildPaperCandidateRows(workspace);
  if (rows.length === 0) {
    return <div className="empty-state">暂无纸面候选</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>开赛</th>
          <th>比赛</th>
          <th>策略</th>
          <th>推荐</th>
          <th>Edge</th>
          <th>风险</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.candidate.match_id}>
            <td>{row.kickoffTime}</td>
            <td>
              {row.league} {row.fixture}
            </td>
            <td>
              <strong>{row.strategyLabel}</strong>
              <span className="muted-text">{row.candidate.strategy_key}</span>
            </td>
            <td>{row.recommendation}</td>
            <td>{row.edge}</td>
            <td>{row.riskText}</td>
            <td>
              <button
                className="inline-action"
                disabled={!row.isRecordable || isBusy}
                onClick={() => onRecord(row.candidate)}
                type="button"
              >
                记录观察
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PaperRecordTable({ isBusy, onEdit, onVoid, records }: PaperRecordTableProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<
    Record<number, { current_market_line: string; current_odds: string; manual_note: string }>
  >({});
  const { pageRecords, pagination, setPage } = useSortedPaginatedRecords(records, 20);

  if (records.length === 0) {
    return <div className="empty-state">暂无纸面记录</div>;
  }

  return (
    <>
      <RecordPagination pagination={pagination} onPageChange={setPage} />
      <table>
        <thead>
          <tr>
            <th>比赛</th>
            <th>策略</th>
            <th>盘口</th>
            <th>赔率</th>
            <th>状态</th>
            <th>赛果</th>
            <th>收益</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {pageRecords.map((record) => {
            const isEditing = editingId === record.id;
            const draft = drafts[record.id] ?? {
              current_market_line: record.current_market_line,
              current_odds: record.current_odds,
              manual_note: record.manual_note ?? ""
            };
            return (
              <tr key={record.id}>
                <td className="record-match-cell">
                  <MatchCell record={record} />
                </td>
                <td>
                  <strong>{record.strategy_display_name}</strong>
                  <span className="muted-text">{record.strategy_key}</span>
                </td>
                <td>
                  {isEditing ? (
                    <input
                      className="table-input"
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [record.id]: { ...draft, current_market_line: event.target.value }
                        }))
                      }
                      value={draft.current_market_line}
                    />
                  ) : (
                    <>
                      {record.recommended_handicap}
                      {record.is_manually_adjusted && <span className="status-pill ready">人工</span>}
                    </>
                  )}
                </td>
                <td>
                  {isEditing ? (
                    <input
                      className="table-input"
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [record.id]: { ...draft, current_odds: event.target.value }
                        }))
                      }
                      value={draft.current_odds}
                    />
                  ) : (
                    record.current_odds
                  )}
                </td>
                <td>{formatPaperRecordStatus(record.status)}</td>
                <td>
                  <SettlementBadge
                    label={formatPaperSettlementResult(record.settlement_result)}
                    result={record.settlement_result}
                  />
                </td>
                <td>
                  <ProfitCell value={record.profit_units} />
                </td>
                <td>
                  {isEditing ? (
                    <div className="inline-actions">
                      <input
                        className="table-input note"
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [record.id]: { ...draft, manual_note: event.target.value }
                          }))
                        }
                        placeholder="备注"
                        value={draft.manual_note}
                      />
                      <button
                        className="inline-action"
                        disabled={isBusy}
                        onClick={() => {
                          onEdit(record, draft);
                          setEditingId(null);
                        }}
                        type="button"
                      >
                        保存
                      </button>
                      <button
                        className="inline-action"
                        disabled={isBusy}
                        onClick={() => setEditingId(null)}
                        type="button"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <div className="inline-actions">
                      <button
                        className="inline-action"
                        disabled={isBusy || record.status === "settled"}
                        onClick={() => setEditingId(record.id)}
                        type="button"
                      >
                        编辑
                      </button>
                      <button
                        className="inline-action"
                        disabled={isBusy || record.status === "void"}
                        onClick={() => onVoid(record)}
                        type="button"
                      >
                        作废
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
