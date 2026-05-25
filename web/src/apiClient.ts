import { mockDashboardData, mockOddsTrends } from "./mockData";
import type {
  DashboardData,
  DashboardSummary,
  DisplayTranslationStatus,
  LeagueCoverage,
  MatchWithOdds,
  MatchOddsTrends,
  RecommendationRecord,
  TeamDisplayNameRow,
  TeamDisplayNameWorkspace,
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
      displayTranslationStatus,
      recommendationRecords
    ] = await Promise.all([
      getJson<DashboardSummary>("/api/dashboard/summary"),
      getJson<LeagueCoverage[]>("/api/leagues/coverage"),
      getJson<WorkerStatus[]>("/api/workers"),
      getJson<UnmatchedMatch[]>("/api/unmatched"),
      getJson<MatchWithOdds[]>("/api/matches/with-odds"),
      getJson<TeamDisplayNameRow[]>("/api/display/missing-team-names"),
      getJson<DisplayTranslationStatus>("/api/display/translation-status"),
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
      doneDisplayTranslationKeys: displayTranslationStatus.done_league_seasons,
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

export async function loadTeamDisplayNameWorkspace(
  leagueId: number,
  season: number
): Promise<TeamDisplayNameWorkspace> {
  return getJson<TeamDisplayNameWorkspace>(
    `/api/display/team-name-workspace?league_id=${leagueId}&season=${season}`
  );
}

export async function markTeamDisplayNameWorkspaceDone(
  leagueId: number,
  season: number
): Promise<{ league_id: number; season: number; is_translation_done: boolean }> {
  return postJson("/api/display/team-name-workspace/done", {
    league_id: leagueId,
    season
  });
}

export async function saveTeamDisplayNames(
  teams: Record<string, string>
): Promise<{ saved_count: number }> {
  return postJson("/api/display/team-names", { teams });
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}
