import { describe, expect, it } from "vitest";

import type { TeamDisplayNameRow, TeamDisplayNameWorkspaceOption } from "./types";
import {
  buildTeamDisplayWorkspaceOptions,
  filterTeamDisplayRows,
  getDisplayNameActionState,
  hasMeaningfulDrafts
} from "./displayNameWorkspace";

const teams: TeamDisplayNameRow[] = [
  {
    league_id: 39,
    league_name: "Premier League",
    league_display_name: "英超",
    season: 2025,
    team_id: 1,
    team_name: "Arsenal",
    team_display_name: "阿森纳",
    is_missing_display_name: false,
    match_count: 38,
    latest_kickoff_time: "2026-05-18T23:00:00+08:00"
  },
  {
    league_id: 39,
    league_name: "Premier League",
    league_display_name: "英超",
    season: 2025,
    team_id: 2,
    team_name: "Wolves",
    team_display_name: null,
    is_missing_display_name: true,
    match_count: 38,
    latest_kickoff_time: "2026-05-18T23:00:00+08:00"
  },
  {
    league_id: 78,
    league_name: "Bundesliga",
    league_display_name: "德甲",
    season: 2025,
    team_id: 3,
    team_name: "Bayern Munich",
    team_display_name: "拜仁慕尼黑",
    is_missing_display_name: false,
    match_count: 34,
    latest_kickoff_time: "2026-05-17T21:30:00+08:00"
  }
];

describe("display name workspace helpers", () => {
  it("filters missing, changed, and text-matched team rows", () => {
    expect(
      filterTeamDisplayRows(teams, {
        draftNames: { Arsenal: "阿森纳", "Bayern Munich": "拜仁" },
        filterText: "",
        statusFilter: "changed"
      }).map((team) => team.team_name)
    ).toEqual(["Bayern Munich"]);

    expect(
      filterTeamDisplayRows(teams, {
        draftNames: {},
        filterText: "",
        statusFilter: "missing"
      }).map((team) => team.team_name)
    ).toEqual(["Wolves"]);

    expect(
      filterTeamDisplayRows(teams, {
        draftNames: {},
        filterText: "拜仁",
        statusFilter: "all"
      }).map((team) => team.team_name)
    ).toEqual(["Bayern Munich"]);
  });

  it("builds league options with unfinished work first", () => {
    const leagues: TeamDisplayNameWorkspaceOption[] = [
      {
        league_id: 78,
        league_name: "Bundesliga",
        league_display_name: "德甲",
        country_or_region: "Germany",
        season: 2025,
        team_count: 18,
        match_count: 306,
        latest_kickoff_time: "2026-05-17T21:30:00+08:00"
      },
      {
        league_id: 39,
        league_name: "Premier League",
        league_display_name: "英超",
        country_or_region: "England",
        season: 2025,
        team_count: 20,
        match_count: 380,
        latest_kickoff_time: "2026-05-18T23:00:00+08:00"
      }
    ];

    expect(buildTeamDisplayWorkspaceOptions(leagues, new Set(["39-2025"]))).toEqual([
      {
        isDone: false,
        key: "78-2025",
        label: "德甲 · 2025",
        leagueId: 78,
        season: 2025
      },
      {
        isDone: true,
        key: "39-2025",
        label: "英超 · 2025 · 已完成",
        leagueId: 39,
        season: 2025
      }
    ]);
  });

  it("builds league options from scheduled-only workspace rows", () => {
    const leagues: TeamDisplayNameWorkspaceOption[] = [
      {
        league_id: 49,
        league_name: "World Cup (World)",
        league_display_name: "世界杯",
        country_or_region: "World",
        season: 2026,
        team_count: 48,
        match_count: 72,
        latest_kickoff_time: "2026-06-28T18:00:00+08:00"
      }
    ];

    expect(buildTeamDisplayWorkspaceOptions(leagues, new Set())).toEqual([
      {
        isDone: false,
        key: "49-2026",
        label: "世界杯 · 2026",
        leagueId: 49,
        season: 2026
      }
    ]);
  });

  it("derives save and mark-done button state from drafts and loading state", () => {
    expect(hasMeaningfulDrafts({ Arsenal: "  ", Wolves: "狼队" })).toBe(true);
    expect(hasMeaningfulDrafts({ Arsenal: "  " })).toBe(false);

    expect(
      getDisplayNameActionState({
        draftNames: { Wolves: "狼队" },
        isSaving: false,
        isTranslationDone: false
      })
    ).toEqual({
      canMarkDone: true,
      canSave: true,
      markDoneLabel: "整联赛已翻译完成",
      saveLabel: "保存当前填写"
    });

    expect(
      getDisplayNameActionState({
        draftNames: { Wolves: "狼队" },
        isSaving: true,
        isTranslationDone: false
      })
    ).toEqual({
      canMarkDone: false,
      canSave: false,
      markDoneLabel: "保存中...",
      saveLabel: "保存中..."
    });
  });
});
