import { mockDashboardData, mockOddsTrends } from "./mockData";
import type {
  DashboardData,
  DashboardSummary,
  LeagueCoverage,
  MatchOddsTrends,
  UnmatchedMatch,
  WorkerStatus
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function loadDashboardData(): Promise<DashboardData> {
  try {
    const [summary, leagues, workers, unmatched] = await Promise.all([
      getJson<DashboardSummary>("/api/dashboard/summary"),
      getJson<LeagueCoverage[]>("/api/leagues/coverage"),
      getJson<WorkerStatus[]>("/api/workers"),
      getJson<UnmatchedMatch[]>("/api/unmatched")
    ]);
    const oddsTrends = await loadFirstOddsTrend(unmatched);
    return {
      source: "api",
      summary,
      leagues,
      workers,
      unmatched,
      oddsTrends
    };
  } catch {
    return mockDashboardData;
  }
}

async function loadFirstOddsTrend(unmatched: UnmatchedMatch[]): Promise<MatchOddsTrends> {
  const matchId = unmatched[0]?.match_id;
  if (!matchId) {
    return mockOddsTrends;
  }
  try {
    return await getJson<MatchOddsTrends>(`/api/matches/${matchId}/odds-trends`);
  } catch {
    return mockOddsTrends;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}
