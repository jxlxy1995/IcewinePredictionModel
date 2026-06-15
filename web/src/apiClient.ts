import {
  mockDashboardData,
  mockMatchDetail,
  mockMatchListWorkspace,
  mockOddsTrends,
  mockPaperRecommendationWorkspace,
  mockTrainingWorkspace,
  mockTeamDisplayNameWorkspaces
} from "./mockData";
import type {
  DashboardData,
  DashboardSummary,
  DisplayTranslationStatus,
  LeagueCoverage,
  MatchDetail,
  MatchListWorkspace,
  MatchSyncRunDetail,
  MatchSyncResponse,
  MatchWithOdds,
  MatchOddsTrends,
  CreatePaperAutomationTaskPayload,
  ManualExecutionTimepointOddsPayload,
  ManualExecutionTimepointOddsResult,
  OddspapiBackfillAudit,
  PaperAutomationTask,
  PaperRecommendationWorkspace,
  RecommendationRecord,
  TeamDisplayNameRow,
  TeamDisplayNameWorkspaceOption,
  TeamDisplayNameWorkspace,
  TrainingRun,
  TrainingWorkspace,
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
      displayTranslationStatus
    ] = await Promise.all([
      getJson<DashboardSummary>("/api/dashboard/summary"),
      getJson<LeagueCoverage[]>("/api/leagues/coverage"),
      getJson<DisplayTranslationStatus>("/api/display/translation-status")
    ]);
    const [
      workers,
      unmatched,
      matchesWithOdds,
      missingTeamDisplayNames,
      teamDisplayWorkspaces,
      recommendationRecords
    ] = await Promise.all([
      getJsonOrFallback<WorkerStatus[]>("/api/workers", []),
      getJsonOrFallback<UnmatchedMatch[]>("/api/unmatched", []),
      getJsonOrFallback<MatchWithOdds[]>("/api/matches/with-odds", []),
      getJsonOrFallback<TeamDisplayNameRow[]>("/api/display/missing-team-names", []),
      getJsonOrFallback<TeamDisplayNameWorkspaceOption[]>("/api/display/team-name-workspaces", []),
      getJsonOrFallback<RecommendationRecord[]>("/api/recommendation-records", [])
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
      teamDisplayWorkspaces,
      doneDisplayTranslationKeys: displayTranslationStatus.done_league_seasons,
      recommendationRecords,
      oddspapiBackfillAudit: mockDashboardData.oddspapiBackfillAudit,
      trainingWorkspace: mockDashboardData.trainingWorkspace,
      paperRecommendations: mockPaperRecommendationWorkspace,
      matchList: mockMatchListWorkspace
    };
  } catch {
    return {
      ...mockDashboardData,
      teamDisplayWorkspaces: mockDashboardData.teamDisplayWorkspaces,
      doneDisplayTranslationKeys: Array.from(fallbackDoneDisplayTranslationKeys)
    };
  }
}

async function loadFirstOddsTrend(matchesWithOdds: MatchWithOdds[]): Promise<MatchOddsTrends> {
  const matchId = matchesWithOdds[0]?.match_id;
  if (!matchId) {
    return mockOddsTrends;
  }
  return getJsonOrFallback<MatchOddsTrends>(`/api/matches/${matchId}/odds-trends`, mockOddsTrends);
}

export async function loadMatchOddsTrend(matchId: number): Promise<MatchOddsTrends> {
  return getJson<MatchOddsTrends>(`/api/matches/${matchId}/odds-trends`);
}

export async function loadOddspapiBackfillAudit(): Promise<OddspapiBackfillAudit> {
  return getJsonOrFallback<OddspapiBackfillAudit>(
    "/api/oddspapi/backfill-audit?season=2025",
    mockDashboardData.oddspapiBackfillAudit
  );
}

export async function loadTrainingWorkspace(): Promise<TrainingWorkspace> {
  return getJsonOrFallback<TrainingWorkspace>(
    "/api/training/workspace",
    mockDashboardData.trainingWorkspace
  );
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

export async function runTrainingWorkflowAction(
  action: "baseline-dataset" | "baseline-dataset-qa" | "market-baseline"
): Promise<TrainingWorkspace> {
  return await postJson<TrainingWorkspace>(`/api/training/${action}`, {});
}

export async function startTrainingFullRefresh(): Promise<TrainingRun> {
  return await postJson<TrainingRun>("/api/training/runs/full-refresh", {});
}

export async function loadLatestTrainingRun(): Promise<TrainingRun | null> {
  return await getJsonOrFallback<TrainingRun | null>("/api/training/runs/latest", null);
}

export type PaperRecommendationWorkspaceParams = {
  end_time?: string;
  start_time?: string;
};

export async function loadPaperRecommendationWorkspace(
  params: PaperRecommendationWorkspaceParams = {}
): Promise<PaperRecommendationWorkspace> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === "") {
      continue;
    }
    query.set(key, value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return await getJson<PaperRecommendationWorkspace>(`/api/paper-recommendations/workspace${suffix}`);
}

export async function loadMatchListWorkspace(params: {
  end_time?: string;
  league_name?: string | null;
  odds_filter?: string | string[];
  search?: string | null;
  start_time?: string;
  status_filter?: string;
} = {}): Promise<MatchListWorkspace> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === "") {
      continue;
    }
    query.set(key, Array.isArray(value) ? value.join(",") : value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  try {
    return await getJson<MatchListWorkspace>(`/api/match-list/workspace${suffix}`);
  } catch {
    return mockMatchListWorkspace;
  }
}

export async function loadMatchDetail(matchId: number): Promise<MatchDetail> {
  try {
    return await getJson<MatchDetail>(`/api/matches/${matchId}/detail`);
  } catch {
    return mockMatchDetail;
  }
}

export async function syncMatchListFixturesResults(days: number): Promise<unknown> {
  return await postJson("/api/match-list/sync/fixtures-results", { days });
}

export async function syncMatchListOdds(days: number): Promise<unknown> {
  return await postJson("/api/match-list/sync/odds", { days });
}

export async function syncFilteredMatchListFixturesResults(filters: {
  end_time?: string;
  league_name?: string | null;
  odds_filter?: string | string[];
  search?: string | null;
  start_time?: string;
  status_filter?: string;
}): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>("/api/match-list/sync/fixtures-results", {
    ...filters,
    odds_filter: serializeOddsFilter(filters.odds_filter)
  });
}

export async function syncFixtureRange(filters: {
  end_time?: string;
  league_name?: string | null;
  start_time?: string;
}): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>("/api/match-list/sync/fixtures-range", filters);
}

export async function syncFilteredMatchListOdds(filters: {
  end_time?: string;
  league_name?: string | null;
  odds_filter?: string | string[];
  search?: string | null;
  start_time?: string;
  status_filter?: string;
}): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>("/api/match-list/sync/odds", {
    ...filters,
    odds_filter: serializeOddsFilter(filters.odds_filter)
  });
}

export async function syncSingleMatchFixturesResults(matchId: number): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>(`/api/matches/${matchId}/sync/fixtures-results`, {});
}

export async function syncSingleMatchOdds(matchId: number): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>(`/api/matches/${matchId}/sync/odds`, {});
}

export async function createManualExecutionTimepointOdds(
  matchId: number,
  payload: ManualExecutionTimepointOddsPayload
): Promise<ManualExecutionTimepointOddsResult> {
  return await postJson<ManualExecutionTimepointOddsResult>(
    `/api/matches/${matchId}/execution-timepoint-odds/manual`,
    payload
  );
}

export async function loadMatchSyncRunDetail(runId: number): Promise<MatchSyncRunDetail> {
  return await getJson<MatchSyncRunDetail>(`/api/data-sync-runs/${runId}/items`);
}

export async function loadPaperAutomationTasks(): Promise<PaperAutomationTask[]> {
  return await getJsonOrFallback<PaperAutomationTask[]>("/api/paper-automation/tasks", []);
}

export async function createPaperAutomationTask(
  payload: CreatePaperAutomationTaskPayload
): Promise<PaperAutomationTask> {
  return await postJson<PaperAutomationTask>("/api/paper-automation/tasks", payload);
}

export async function loadPaperAutomationTask(taskId: number): Promise<PaperAutomationTask> {
  return await getJson<PaperAutomationTask>(`/api/paper-automation/tasks/${taskId}`);
}

export async function cancelPaperAutomationTask(taskId: number): Promise<PaperAutomationTask> {
  return await postJson<PaperAutomationTask>(`/api/paper-automation/tasks/${taskId}/cancel`, {});
}

function serializeOddsFilter(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value.join(",") : value;
}

export async function recordPaperCandidate(
  matchId: number,
  strategyKey?: string,
  params: PaperRecommendationWorkspaceParams = {}
): Promise<unknown> {
  return await postJson("/api/paper-recommendations/records", {
    match_id: matchId,
    strategy_key: strategyKey,
    ...params
  });
}

export async function recordPaperCandidates(
  candidates: Array<{ match_id: number; strategy_key?: string }>,
  params: PaperRecommendationWorkspaceParams = {}
): Promise<PaperRecommendationWorkspace> {
  return await postJson<PaperRecommendationWorkspace>("/api/paper-recommendations/records/batch", {
    candidates,
    ...params
  });
}

export async function editPaperRecord(
  recordId: number,
  payload: { current_market_line: string; current_odds: string; manual_note: string }
): Promise<unknown> {
  return await patchJson(`/api/paper-recommendations/records/${recordId}`, payload);
}

export async function settlePaperRecords(): Promise<unknown> {
  return await postJson("/api/paper-recommendations/settle", {});
}

export async function voidPaperRecord(recordId: number): Promise<unknown> {
  return await postJson(`/api/paper-recommendations/records/${recordId}/void`, {});
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(await formatApiError(response, path));
  }
  return response.json() as Promise<T>;
}

async function getJsonOrFallback<T>(path: string, fallback: T): Promise<T> {
  try {
    return await getJson<T>(path);
  } catch {
    return fallback;
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await formatApiError(response, path));
  }
  return response.json() as Promise<T>;
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    method: "PATCH"
  });
  if (!response.ok) {
    throw new Error(await formatApiError(response, path));
  }
  return response.json() as Promise<T>;
}

async function formatApiError(response: Response, path: string): Promise<string> {
  const fallback = `API request failed: ${path}`;
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail) {
        return `${fallback}: ${String(payload.detail)}`;
      }
    } else {
      const text = await response.text();
      if (text) {
        return `${fallback}: ${text}`;
      }
    }
  } catch {
    return fallback;
  }
  return fallback;
}
