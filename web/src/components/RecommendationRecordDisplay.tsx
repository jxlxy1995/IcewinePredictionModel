import { useEffect, useState } from "react";

import {
  buildPagination,
  formatScore,
  paginateRecords,
  settlementTone,
  sortRecordsByKickoffDesc,
  type PaginationState
} from "../recommendationRecordDisplay";

export type MatchDisplayRecord = {
  id: number;
  kickoff_time: string;
  league_name: string;
  league_display_name?: string | null;
  home_team_name: string;
  home_team_display_name?: string | null;
  home_team_logo_url?: string | null;
  away_team_name: string;
  away_team_display_name?: string | null;
  away_team_logo_url?: string | null;
  home_score?: number | null;
  away_score?: number | null;
};

type MatchCellProps = {
  record: MatchDisplayRecord;
};

type SettlementBadgeProps = {
  label: string;
  result: string | null;
};

type ProfitCellProps = {
  value: string | null;
};

type RecordPaginationProps = {
  pagination: PaginationState;
  onPageChange: (page: number) => void;
};

export function MatchCell({ record }: MatchCellProps) {
  return (
    <div className="record-match">
      <div className="record-match-meta">
        <span>{record.league_display_name ?? record.league_name}</span>
        <span>{record.kickoff_time}</span>
      </div>
      <div className="record-scoreline">
        <TeamMiniBadge
          logoUrl={record.home_team_logo_url}
          name={record.home_team_display_name ?? record.home_team_name}
        />
        <span className="record-score">{formatScore(record.home_score, record.away_score)}</span>
        <TeamMiniBadge
          align="right"
          logoUrl={record.away_team_logo_url}
          name={record.away_team_display_name ?? record.away_team_name}
        />
      </div>
    </div>
  );
}

export function SettlementBadge({ label, result }: SettlementBadgeProps) {
  return <span className={`settlement-badge ${settlementTone(result)}`}>{label}</span>;
}

export function ProfitCell({ value }: ProfitCellProps) {
  const numeric = value === null ? null : Number(value);
  const tone = numeric === null ? "pending" : numeric > 0 ? "win" : numeric < 0 ? "loss" : "push";
  return <span className={`profit-value ${tone}`}>{value ?? "-"}</span>;
}

export function RecordPagination({ pagination, onPageChange }: RecordPaginationProps) {
  const [draftPage, setDraftPage] = useState(String(pagination.page));

  useEffect(() => {
    setDraftPage(String(pagination.page));
  }, [pagination.page]);

  return (
    <div className="record-pagination">
      <span>
        共 {pagination.totalItems.toLocaleString()} 条 / 第 {pagination.page} 页，共{" "}
        {pagination.pageCount} 页
      </span>
      <div className="record-pagination-controls">
        <button
          className="inline-action"
          disabled={pagination.page <= 1}
          onClick={() => onPageChange(pagination.page - 1)}
          type="button"
        >
          上一页
        </button>
        <input
          className="page-input"
          min={1}
          max={pagination.pageCount}
          onChange={(event) => setDraftPage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onPageChange(Number(draftPage));
            }
          }}
          type="number"
          value={draftPage}
        />
        <button className="inline-action" onClick={() => onPageChange(Number(draftPage))} type="button">
          跳转
        </button>
        <button
          className="inline-action"
          disabled={pagination.page >= pagination.pageCount}
          onClick={() => onPageChange(pagination.page + 1)}
          type="button"
        >
          下一页
        </button>
      </div>
    </div>
  );
}

export function useSortedPaginatedRecords<T extends MatchDisplayRecord>(
  records: T[],
  pageSize = 20
) {
  const [page, setPage] = useState(1);
  const sortedRecords = sortRecordsByKickoffDesc(records);
  const pagination = buildPagination({
    totalItems: sortedRecords.length,
    page,
    pageSize
  });
  const pageRecords = paginateRecords(sortedRecords, pagination);

  useEffect(() => {
    setPage((current) =>
      buildPagination({ totalItems: sortedRecords.length, page: current, pageSize }).page
    );
  }, [pageSize, sortedRecords.length]);

  return {
    pageRecords,
    pagination,
    setPage
  };
}

function TeamMiniBadge({
  align,
  logoUrl,
  name
}: {
  align?: "right";
  logoUrl?: string | null;
  name: string;
}) {
  return (
    <span className={`team-mini-badge ${align === "right" ? "right" : ""}`}>
      {logoUrl ? <img alt="" src={logoUrl} /> : <span className="team-logo-placeholder" />}
      <span>{name}</span>
    </span>
  );
}
