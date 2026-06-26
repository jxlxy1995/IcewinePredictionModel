import { Fragment, useState } from "react";
import { Trash2 } from "lucide-react";

import type { PaperCandidate, PaperRecord } from "../types";
import {
  buildPaperConfidenceSimulationRows,
  buildPaperDiagnosticCards,
  buildPaperCandidateGroups,
  explainPaperCandidateSignal,
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
  onRecordAll: (candidates: PaperCandidate[]) => void;
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

type PaperConfidenceSimulationTableProps = {
  defaultExpandedGroupKeys?: string[];
  isBusy?: boolean;
  onDelete?: (record: PaperRecord) => void;
  workspace: PaperRecommendationWorkspace;
};

export function PaperCandidateTable({
  isBusy,
  onRecordAll,
  onRecord,
  workspace
}: PaperCandidateTableProps) {
  const [expandedMatches, setExpandedMatches] = useState<Set<string>>(() => new Set());
  const diagnosticCards = buildPaperDiagnosticCards(workspace);
  const groups = buildPaperCandidateGroups(workspace);
  if (groups.length === 0) {
    return (
      <>
        <PaperDiagnostics cards={diagnosticCards} />
        <div className="empty-state">暂无纸面候选</div>
      </>
    );
  }

  const toggleExpanded = (groupKey: string) => {
    setExpandedMatches((current) => {
      const next = new Set(current);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  };

  return (
    <>
      <PaperDiagnostics cards={diagnosticCards} />
      <table>
        <thead>
          <tr>
            <th>开赛</th>
            <th>比赛</th>
            <th>主推荐</th>
            <th>候选</th>
            <th>Edge</th>
            <th>风险</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const isExpanded = expandedMatches.has(group.groupKey);
            return (
              <Fragment key={`match-${group.groupKey}`}>
                <tr className="paper-candidate-match-row">
                  <td>{group.kickoffTime}</td>
                  <td>
                    <strong>
                      {group.league} {group.fixture}
                    </strong>
                    <span className="muted-text">match #{group.matchId}</span>
                  </td>
                  <td>
                    <strong>{group.main.recommendation}</strong>
                    <span className="muted-text">{group.main.strategyLabel}</span>
                  </td>
                  <td>
                    {group.signalCount} 条
                    <span className="muted-text">{group.recordableCount} 条可记录</span>
                  </td>
                  <td>{group.main.edge}</td>
                  <td>{group.main.riskText}</td>
                  <td>
                    <div className="inline-actions">
                      <button
                        className="inline-action"
                        onClick={() => toggleExpanded(group.groupKey)}
                        type="button"
                      >
                        {isExpanded ? "收起" : "展开"}
                      </button>
                      <button
                        className="inline-action"
                        disabled={!group.main.isRecordable || isBusy}
                        onClick={() => onRecord(group.main.candidate)}
                        type="button"
                      >
                        记录主推
                      </button>
                      <button
                        className="inline-action"
                        disabled={group.recordableSignals.length === 0 || isBusy}
                        onClick={() =>
                          onRecordAll(group.recordableSignals.map((signal) => signal.candidate))
                        }
                        type="button"
                      >
                        记录全部
                      </button>
                    </div>
                  </td>
                </tr>
                {isExpanded &&
                  group.signals.map((signal) => {
                    const explanation = explainPaperCandidateSignal(
                      signal.candidate,
                      workspace.diagnostics?.edge_threshold
                    );
                    return (
                      <Fragment key={`signal-${signal.signalKey}`}>
                        <tr className="paper-candidate-signal-row">
                          <td />
                          <td>
                            <span className="muted-text">策略信号</span>
                          </td>
                          <td>
                            <strong>{signal.strategyLabel}</strong>
                            <span className="muted-text">{signal.candidate.strategy_key}</span>
                          </td>
                          <td>{signal.recommendation}</td>
                          <td>{signal.edge}</td>
                          <td>{signal.riskText}</td>
                          <td>
                            <button
                              className="inline-action"
                              disabled={!signal.isRecordable || isBusy}
                              onClick={() => onRecord(signal.candidate)}
                              type="button"
                            >
                              记录观察
                            </button>
                          </td>
                        </tr>
                        <tr className="paper-signal-explanation-row">
                          <td />
                          <td colSpan={6}>
                            <div className="paper-signal-explanation">
                              <strong>{explanation.title}</strong>
                              <span>{explanation.formula}</span>
                              <span>{explanation.verdict}</span>
                              <span>{explanation.facts.join(" / ")}</span>
                            </div>
                          </td>
                        </tr>
                      </Fragment>
                    );
                  })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function PaperDiagnostics({
  cards
}: {
  cards: Array<{ label: string; meta: string; value: string }>;
}) {
  return (
    <div className="paper-diagnostic-grid">
      {cards.map((card) => (
        <div className="paper-diagnostic-card" key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <em>{card.meta}</em>
        </div>
      ))}
    </div>
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

export function PaperConfidenceSimulationTable({
  defaultExpandedGroupKeys = [],
  isBusy = false,
  onDelete,
  workspace
}: PaperConfidenceSimulationTableProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    () => new Set(defaultExpandedGroupKeys)
  );
  const rows = buildPaperConfidenceSimulationRows(workspace);
  const { pageRecords, pagination, setPage } = useSortedPaginatedRecords(rows, 20);
  if (rows.length === 0) {
    return <div className="empty-state">暂无纸面推荐记录</div>;
  }
  const recordsById = new Map(workspace.records.map((record) => [record.id, record]));
  const toggleExpanded = (groupKey: string) => {
    setExpandedGroups((current) => {
      const next = new Set(current);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  };
  return (
    <>
      <RecordPagination pagination={pagination} onPageChange={setPage} />
      <table>
        <thead>
          <tr>
            <th>比赛</th>
            <th>推荐</th>
            <th>信心</th>
            <th>手数</th>
            <th>结算</th>
            <th>1手收益</th>
            <th>动态收益</th>
            <th>信号</th>
          </tr>
        </thead>
        <tbody>
          {pageRecords.map((row) => {
            const isExpanded = expandedGroups.has(row.group.group_key);
            const signalRecords = row.signalRecordIds
              .map((recordId) => recordsById.get(recordId))
              .filter((record): record is PaperRecord => record !== undefined);
            const representativeRecord = recordsById.get(row.group.representative_record_id);
            return (
              <Fragment key={row.group.group_key}>
                <tr>
                  <td className="record-match-cell">
                    <MatchCell record={row} />
                  </td>
                  <td>
                    <strong>{row.recommendation}</strong>
                    <span className="muted-text">{row.familyCombo}</span>
                  </td>
                  <td>{row.confidenceScore}</td>
                  <td>
                    {row.suggestedStakeUnits}
                    {row.capReason !== "none" && (
                      <span className="muted-text">{formatCapReason(row.capReason)}</span>
                    )}
                  </td>
                  <td>
                    <SettlementBadge
                      label={formatPaperSettlementResult(row.group.settlement_result)}
                      result={row.group.settlement_result}
                    />
                  </td>
                  <td>
                    <ProfitCell value={row.flatProfitUnits} />
                  </td>
                  <td>
                    <ProfitCell value={row.weightedProfitUnits} />
                  </td>
                  <td className="paper-row-actions-cell">
                    {onDelete && representativeRecord && (
                      <button
                        aria-label={`delete paper record #${representativeRecord.id}`}
                        className="paper-delete-button"
                        disabled={isBusy}
                        onClick={() => onDelete(representativeRecord)}
                        title="delete paper record"
                        type="button"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                    <button
                      className="inline-action"
                      onClick={() => toggleExpanded(row.group.group_key)}
                      type="button"
                    >
                      {isExpanded ? "收起" : `查看信号 ${signalRecords.length}`}
                    </button>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="paper-candidate-signal-row">
                    <td />
                    <td colSpan={8}>
                      <table className="nested-table">
                        <thead>
                          <tr>
                            <th>信号</th>
                            <th>盘口</th>
                            <th>赔率</th>
                            <th>Edge</th>
                            <th>操作</th>
                            <th>结算</th>
                            <th>1手收益</th>
                          </tr>
                        </thead>
                        <tbody>
                          {signalRecords.map((record) => (
                            <tr key={record.id}>
                              <td>
                                <strong>{record.strategy_display_name}</strong>
                                <span className="muted-text">{record.strategy_key}</span>
                              </td>
                              <td>{record.recommended_handicap}</td>
                              <td>{record.current_odds}</td>
                              <td>{record.edge}</td>
                              <td>
                                {onDelete && (
                                  <button
                                    aria-label={`delete paper record #${record.id}`}
                                    className="paper-delete-button"
                                    disabled={isBusy}
                                    onClick={() => onDelete(record)}
                                    title="delete paper record"
                                    type="button"
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                )}
                              </td>
                              <td>
                                <SettlementBadge
                                  label={formatPaperSettlementResult(record.settlement_result)}
                                  result={record.settlement_result}
                                />
                              </td>
                              <td>
                                <ProfitCell value={record.profit_units} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function formatCapReason(value: string): string {
  const labels: Record<string, string> = {
    same_family_cap: "同源信号封顶",
    single_family_limited_history: "样本封顶"
  };
  return labels[value] ?? value;
}
