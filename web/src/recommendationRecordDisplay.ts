export type MinimalTimedRecord = {
  id: number;
  kickoff_time: string;
};

export type PaginationState = {
  page: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
};

export type SettlementTone = "half-loss" | "half-win" | "loss" | "pending" | "push" | "win";

export function sortRecordsByKickoffDesc<T extends MinimalTimedRecord>(records: T[]): T[] {
  return [...records].sort((first, second) => {
    const timeDelta =
      new Date(second.kickoff_time).getTime() - new Date(first.kickoff_time).getTime();
    if (timeDelta !== 0) {
      return timeDelta;
    }
    return second.id - first.id;
  });
}

export function formatScore(
  homeScore: number | null | undefined,
  awayScore: number | null | undefined
): string {
  if (homeScore === null || homeScore === undefined || awayScore === null || awayScore === undefined) {
    return "vs";
  }
  return `${homeScore}-${awayScore}`;
}

export function settlementTone(value: string | null): SettlementTone {
  const tones: Record<string, SettlementTone> = {
    half_loss: "half-loss",
    half_win: "half-win",
    loss: "loss",
    push: "push",
    win: "win"
  };
  return value ? tones[value] ?? "pending" : "pending";
}

export function buildPagination({
  totalItems,
  page,
  pageSize
}: {
  totalItems: number;
  page: number;
  pageSize: number;
}): PaginationState {
  const normalizedPageSize = Math.max(1, pageSize);
  const pageCount = Math.max(1, Math.ceil(totalItems / normalizedPageSize));
  const normalizedPage = Math.min(Math.max(1, page), pageCount);
  return {
    page: normalizedPage,
    pageCount,
    pageSize: normalizedPageSize,
    totalItems
  };
}

export function paginateRecords<T>(records: T[], pagination: PaginationState): T[] {
  const start = (pagination.page - 1) * pagination.pageSize;
  return records.slice(start, start + pagination.pageSize);
}
