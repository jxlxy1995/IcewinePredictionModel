import type { TeamDisplayNameRow, TeamDisplayNameWorkspaceOption } from "./types";

export type DisplayNameStatusFilter = "all" | "missing" | "changed";

export type BuiltTeamDisplayWorkspaceOption = {
  isDone: boolean;
  key: string;
  label: string;
  leagueId: number;
  season: number;
};

export type DisplayNameActionState = {
  canMarkDone: boolean;
  canSave: boolean;
  markDoneLabel: string;
  saveLabel: string;
};

export function filterTeamDisplayRows(
  teams: TeamDisplayNameRow[],
  {
    draftNames,
    filterText,
    statusFilter
  }: {
    draftNames: Record<string, string>;
    filterText: string;
    statusFilter: DisplayNameStatusFilter;
  }
): TeamDisplayNameRow[] {
  const normalizedFilterText = filterText.trim().toLowerCase();
  return teams.filter((team) => {
    if (statusFilter === "missing" && !isMissingDisplayName(team)) {
      return false;
    }
    if (statusFilter === "changed" && !hasChangedDraft(team, draftNames)) {
      return false;
    }
    if (!normalizedFilterText) {
      return true;
    }
    return `${team.team_display_name ?? ""} ${team.team_name}`
      .toLowerCase()
      .includes(normalizedFilterText);
  });
}

export function buildTeamDisplayWorkspaceOptions(
  leagues: TeamDisplayNameWorkspaceOption[],
  doneKeys: Set<string>
): BuiltTeamDisplayWorkspaceOption[] {
  return Array.from(
    new Map(
      leagues
        .filter((league) => league.season != null)
        .map((league) => {
          const key = `${league.league_id}-${league.season}`;
          const displayName = league.league_display_name ?? league.league_name;
          const isDone = doneKeys.has(key);
          return [
            key,
            {
              isDone,
              key,
              label: `${displayName} · ${league.season}${isDone ? " · 已完成" : ""}`,
              leagueId: league.league_id,
              season: league.season
            }
          ];
        })
    ).values()
  ).sort((left, right) => {
    if (left.isDone !== right.isDone) {
      return left.isDone ? 1 : -1;
    }
    return left.label.localeCompare(right.label);
  });
}

export function getDisplayNameActionState({
  draftNames,
  isSaving,
  isTranslationDone
}: {
  draftNames: Record<string, string>;
  isSaving: boolean;
  isTranslationDone: boolean;
}): DisplayNameActionState {
  if (isSaving) {
    return {
      canMarkDone: false,
      canSave: false,
      markDoneLabel: "保存中...",
      saveLabel: "保存中..."
    };
  }
  return {
    canMarkDone: !isTranslationDone,
    canSave: hasMeaningfulDrafts(draftNames),
    markDoneLabel: isTranslationDone ? "已完成校验" : "整联赛已翻译完成",
    saveLabel: "保存当前填写"
  };
}

export function hasMeaningfulDrafts(draftNames: Record<string, string>): boolean {
  return Object.values(draftNames).some((displayName) => displayName.trim().length > 0);
}

function isMissingDisplayName(team: TeamDisplayNameRow): boolean {
  return team.is_missing_display_name === true || !team.team_display_name;
}

function hasChangedDraft(
  team: TeamDisplayNameRow,
  draftNames: Record<string, string>
): boolean {
  const draft = draftNames[team.team_name]?.trim() ?? "";
  if (!draft) {
    return false;
  }
  return draft !== (team.team_display_name ?? "");
}
