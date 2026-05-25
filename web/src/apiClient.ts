import { mockDashboardData, mockOddsTrends } from "./mockData";
import type {
  DashboardData,
  DashboardSummary,
  LeagueCoverage,
  MatchWithOdds,
  MatchOddsTrends,
  MissingTeamDisplayName,
  RecommendationRecord,
  UnmatchedMatch,
  WorkerStatus
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function loadDashboardData(): Promise<DashboardData> {
  try {
    const [
      summary,
      leagues,
      workers,
      unmatched,
      matchesWithOdds,
      missingTeamDisplayNames,
      recommendationRecords
    ] = await Promise.all([
      getJson<DashboardSummary>("/api/dashboard/summary"),
      getJson<LeagueCoverage[]>("/api/leagues/coverage"),
      getJson<WorkerStatus[]>("/api/workers"),
      getJson<UnmatchedMatch[]>("/api/unmatched"),
      getJson<MatchWithOdds[]>("/api/matches/with-odds"),
      getJson<MissingTeamDisplayName[]>("/api/display/missing-team-names"),
      getJson<RecommendationRecord[]>("/api/recommendation-records")
    ]);
    const oddsTrends = await loadFirstOddsTrend(matchesWithOdds);
    return {
      source: "api",
      summary,
      leagues,
      workers,
      unmatched,
      oddsTrends,
      matchesWithOdds,
      missingTeamDisplayNames,
      recommendationRecords
    };
  } catch {
    return mockDashboardData;
  }
}

async function loadFirstOddsTrend(matchesWithOdds: MatchWithOdds[]): Promise<MatchOddsTrends> {
  const matchId = matchesWithOdds[0]?.match_id;
  if (!matchId) {
    return mockOddsTrends;
  }
  return loadMatchOddsTrend(matchId);
}

export async function loadMatchOddsTrend(matchId: number): Promise<MatchOddsTrends> {
  return getJson<MatchOddsTrends>(`/api/matches/${matchId}/odds-trends`);
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}
