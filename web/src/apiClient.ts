import { mockDashboardData, mockOddsTrends, mockTeamDisplayNameWorkspaces } from "./mockData";
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
const fallbackSavedTeamNames: Record<string, string> = {};
const fallbackDoneDisplayTranslationKeys = new Set(mockDashboardData.doneDisplayTranslationKeys);

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
    return {
      ...mockDashboardData,
      doneDisplayTranslationKeys: Array.from(fallbackDoneDisplayTranslationKeys)
    };
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
  try {
    return await getJson<TeamDisplayNameWorkspace>(
      `/api/display/team-name-workspace?league_id=${leagueId}&season=${season}`
    );
  } catch {
    const workspace =
      mockTeamDisplayNameWorkspaces.find(
        (item) => item.league_id === leagueId && item.season === season
      ) ?? mockTeamDisplayNameWorkspaces[0];
    return {
      ...workspace,
      is_translation_done: fallbackDoneDisplayTranslationKeys.has(
        `${workspace.league_id}-${workspace.season}`
      ),
      teams: workspace.teams.map((team) => {
        const savedDisplayName = fallbackSavedTeamNames[team.team_name];
        if (!savedDisplayName) {
          return team;
        }
        return {
          ...team,
          is_missing_display_name: false,
          team_display_name: savedDisplayName
        };
      })
    };
  }
}

export async function markTeamDisplayNameWorkspaceDone(
  leagueId: number,
  season: number
): Promise<{ league_id: number; season: number; is_translation_done: boolean }> {
  try {
    return await postJson("/api/display/team-name-workspace/done", {
      league_id: leagueId,
      season
    });
  } catch {
    fallbackDoneDisplayTranslationKeys.add(`${leagueId}-${season}`);
    return { is_translation_done: true, league_id: leagueId, season };
  }
}

export async function saveTeamDisplayNames(
  teams: Record<string, string>
): Promise<{ saved_count: number }> {
  try {
    return await postJson("/api/display/team-names", { teams });
  } catch {
    Object.assign(fallbackSavedTeamNames, teams);
    return { saved_count: Object.keys(teams).length };
  }
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
