import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  CircleAlert,
  Database,
  Languages,
  ListChecks,
  Radio
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  loadDashboardData,
  loadMatchOddsTrend,
  markTeamDisplayNameWorkspaceDone,
  saveTeamDisplayNames,
  loadTeamDisplayNameWorkspace
} from "../apiClient";
import { LeagueCoverageTable } from "../components/LeagueCoverageTable";
import { MetricCard } from "../components/MetricCard";
import { OddsTrendPanel } from "../components/OddsTrendPanel";
import { Panel } from "../components/Panel";
import { RecommendationRecordTable } from "../components/RecommendationRecordTable";
import { TeamDisplayNameEditor } from "../components/TeamDisplayNameEditor";
import { UnmatchedTable } from "../components/UnmatchedTable";
import {
  buildTeamDisplayWorkspaceOptions,
  filterTeamDisplayRows,
  getDisplayNameActionState,
  hasMeaningfulDrafts
} from "../displayNameWorkspace";
import { WorkerStatusTable } from "../components/WorkerStatusTable";
import { mockDashboardData } from "../mockData";
import type { DisplayNameStatusFilter } from "../displayNameWorkspace";
import type { DashboardData, TeamDisplayNameWorkspace, MatchOddsTrends } from "../types";

type ViewKey =
  | "overview"
  | "coverage"
  | "workers"
  | "unmatched"
  | "displayNames"
  | "odds"
  | "records";

type NavItem = {
  key: ViewKey;
  label: string;
  icon: LucideIcon;
};

const navItems: NavItem[] = [
  { key: "overview", label: "总览", icon: Activity },
  { key: "coverage", label: "覆盖率", icon: Database },
  { key: "workers", label: "Worker", icon: Radio },
  { key: "unmatched", label: "未匹配", icon: CircleAlert },
  { key: "displayNames", label: "中文名", icon: Languages },
  { key: "odds", label: "赔率走势", icon: BarChart3 },
  { key: "records", label: "推荐记录", icon: ListChecks }
];

const viewText: Record<ViewKey, { title: string; subtitle: string }> = {
  overview: {
    title: "控制台总览",
    subtitle: "本地数据回填、赔率覆盖和模型推荐的工作台"
  },
  coverage: {
    title: "联赛覆盖率",
    subtitle: "按联赛和赛季检查历史赔率快照覆盖情况"
  },
  workers: {
    title: "Worker 状态",
    subtitle: "查看后台回填进程、批次参数和日志路径"
  },
  unmatched: {
    title: "未匹配比赛",
    subtitle: "集中处理外部数据源队名差异和匹配失败记录"
  },
  displayNames: {
    title: "中文名维护",
    subtitle: "按联赛和赛季检查缺失中文显示名的球队"
  },
  odds: {
    title: "赔率走势",
    subtitle: "查看单场亚盘和大小球主盘口变化"
  },
  records: {
    title: "推荐记录",
    subtitle: "后续用于展示推荐、信心等级、手数和复盘结果"
  }
};

export function DashboardPage() {
  const [activeView, setActiveView] = useState<ViewKey>("overview");
  const [data, setData] = useState<DashboardData>(mockDashboardData);
  const [isLoading, setIsLoading] = useState(true);
  const [oddsTrends, setOddsTrends] = useState<MatchOddsTrends>(mockDashboardData.oddsTrends);
  const [selectedOddsMatchId, setSelectedOddsMatchId] = useState<number>(
    mockDashboardData.oddsTrends.match_id
  );
  const [oddsTrendError, setOddsTrendError] = useState<string | null>(null);
  const [coverageFilter, setCoverageFilter] = useState("");
  const [displayNameFilter, setDisplayNameFilter] = useState("");
  const [displayNameStatusFilter, setDisplayNameStatusFilter] =
    useState<DisplayNameStatusFilter>("all");
  const [teamDisplayWorkspace, setTeamDisplayWorkspace] = useState<TeamDisplayNameWorkspace | null>(
    null
  );
  const [displayWorkspaceError, setDisplayWorkspaceError] = useState<string | null>(null);
  const [displayWorkspaceMessage, setDisplayWorkspaceMessage] = useState<string | null>(null);
  const [teamDisplayDraftNames, setTeamDisplayDraftNames] = useState<Record<string, string>>({});
  const [isSavingDisplayNames, setIsSavingDisplayNames] = useState(false);
  const [doneDisplayTranslationKeys, setDoneDisplayTranslationKeys] = useState<Set<string>>(
    new Set(mockDashboardData.doneDisplayTranslationKeys)
  );
  const [coverageSort, setCoverageSort] = useState<
    "coverage_desc" | "coverage_asc" | "unmatched_desc"
  >("coverage_desc");

  useEffect(() => {
    let isMounted = true;
    loadDashboardData().then((loadedData) => {
      if (!isMounted) {
        return;
      }
      setData(loadedData);
      setDoneDisplayTranslationKeys(new Set(loadedData.doneDisplayTranslationKeys));
      setOddsTrends(loadedData.oddsTrends);
      setSelectedOddsMatchId(loadedData.oddsTrends.match_id);
      const firstLeague = loadedData.leagues[0];
      if (firstLeague?.season != null) {
        loadTeamDisplayNameWorkspace(firstLeague.league_id, firstLeague.season)
          .then((workspace) => {
            if (isMounted) {
              setTeamDisplayWorkspace(workspace);
            }
          })
          .catch(() => {
            if (isMounted) {
              setDisplayWorkspaceError("读取球队中文名维护列表失败");
            }
          });
      }
      setIsLoading(false);
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const activeText = viewText[activeView];
  const statusText = useMemo(() => {
    if (isLoading) {
      return "正在加载";
    }
    return data.source === "api" ? "真实接口" : "Mock 数据";
  }, [data.source, isLoading]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">冰酒预测</div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={activeView === item.key ? "active" : ""}
                key={item.key}
                onClick={() => setActiveView(item.key)}
                type="button"
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="content">
        <section className="topbar">
          <div>
            <h1>{activeText.title}</h1>
            <p>{activeText.subtitle}</p>
          </div>
          <span className="status-dot">{statusText}</span>
        </section>

        {activeView === "overview" && <OverviewView data={data} oddsTrends={oddsTrends} />}
        {activeView === "coverage" && (
          <CoverageView
            data={data}
            filterText={coverageFilter}
            onFilterTextChange={setCoverageFilter}
            onSortChange={setCoverageSort}
            sortBy={coverageSort}
          />
        )}
        {activeView === "workers" && <WorkersView data={data} />}
        {activeView === "unmatched" && <UnmatchedView data={data} />}
        {activeView === "displayNames" && (
          <DisplayNamesView
            data={data}
            doneKeys={doneDisplayTranslationKeys}
            filterText={displayNameFilter}
            isSaving={isSavingDisplayNames}
            onFilterTextChange={setDisplayNameFilter}
            onStatusFilterChange={setDisplayNameStatusFilter}
            draftNames={teamDisplayDraftNames}
            onDraftNamesChange={setTeamDisplayDraftNames}
            onMarkDone={(leagueId, season) => {
              setDisplayWorkspaceError(null);
              setDisplayWorkspaceMessage(null);
              setIsSavingDisplayNames(true);
              saveCurrentTeamDisplayDrafts(teamDisplayDraftNames)
                .then(() => markTeamDisplayNameWorkspaceDone(leagueId, season))
                .then(() => {
                  const doneKey = `${leagueId}-${season}`;
                  setDoneDisplayTranslationKeys(new Set([...doneDisplayTranslationKeys, doneKey]));
                  setTeamDisplayWorkspace((current) =>
                    current && current.league_id === leagueId && current.season === season
                      ? { ...current, is_translation_done: true }
                      : current
                  );
                  setTeamDisplayDraftNames({});
                  setDisplayWorkspaceMessage("已保存当前填写并标记完成");
                })
                .catch(() => setDisplayWorkspaceError("保存或标记中文名校验完成失败"))
                .finally(() => setIsSavingDisplayNames(false));
            }}
            onSaveDrafts={() => {
              setDisplayWorkspaceError(null);
              setDisplayWorkspaceMessage(null);
              setIsSavingDisplayNames(true);
              saveCurrentTeamDisplayDrafts(teamDisplayDraftNames)
                .then((savedCount) => {
                  setTeamDisplayDraftNames({});
                  setDisplayWorkspaceMessage(`已保存 ${savedCount} 个中文名`);
                  if (teamDisplayWorkspace) {
                    return loadTeamDisplayNameWorkspace(
                      teamDisplayWorkspace.league_id,
                      teamDisplayWorkspace.season
                    ).then(setTeamDisplayWorkspace);
                  }
                  return undefined;
                })
                .catch(() => setDisplayWorkspaceError("保存中文名失败"))
                .finally(() => setIsSavingDisplayNames(false));
            }}
            onWorkspaceChange={(leagueId, season) => {
              if (
                hasMeaningfulDrafts(teamDisplayDraftNames) &&
                !window.confirm("当前有未保存的中文名草稿，切换联赛会清空这些填写。确认切换吗？")
              ) {
                return;
              }
              setDisplayWorkspaceError(null);
              setDisplayWorkspaceMessage(null);
              setTeamDisplayDraftNames({});
              loadTeamDisplayNameWorkspace(leagueId, season)
                .then(setTeamDisplayWorkspace)
                .catch(() => setDisplayWorkspaceError("读取球队中文名维护列表失败"));
            }}
            statusFilter={displayNameStatusFilter}
            workspace={teamDisplayWorkspace}
            workspaceError={displayWorkspaceError}
            workspaceMessage={displayWorkspaceMessage}
          />
        )}
        {activeView === "odds" && (
          <OddsView
            data={data}
            errorText={oddsTrendError}
            oddsTrends={oddsTrends}
            onMatchChange={(matchId) => {
              setSelectedOddsMatchId(matchId);
              setOddsTrendError(null);
              loadMatchOddsTrend(matchId)
                .then(setOddsTrends)
                .catch(() => {
                  setOddsTrendError("读取该场赔率走势失败，请稍后重试");
                });
            }}
            selectedMatchId={selectedOddsMatchId}
          />
        )}
        {activeView === "records" && <RecordsView data={data} />}
      </main>
    </div>
  );
}

function OverviewView({ data, oddsTrends }: { data: DashboardData; oddsTrends: MatchOddsTrends }) {
  return (
    <>
      <SummaryMetrics data={data} />
      <section className="grid">
        <Panel title="联赛覆盖率">
          <LeagueCoverageTable leagues={data.leagues.slice(0, 6)} />
        </Panel>
        <Panel title="Worker 状态">
          <WorkerStatusTable workers={data.workers} />
        </Panel>
      </section>
      <section className="grid">
        <Panel title="单场赔率走势">
          <OddsTrendPanel trends={oddsTrends} />
        </Panel>
        <Panel title="待处理未匹配">
          <UnmatchedTable matches={data.unmatched.slice(0, 6)} />
        </Panel>
      </section>
    </>
  );
}

function CoverageView({
  data,
  filterText,
  sortBy,
  onFilterTextChange,
  onSortChange
}: {
  data: DashboardData;
  filterText: string;
  sortBy: "coverage_desc" | "coverage_asc" | "unmatched_desc";
  onFilterTextChange: (value: string) => void;
  onSortChange: (value: "coverage_desc" | "coverage_asc" | "unmatched_desc") => void;
}) {
  return (
    <>
      <SummaryMetrics data={data} />
      <Panel title="全部联赛覆盖率">
        <div className="table-toolbar">
          <input
            onChange={(event) => onFilterTextChange(event.target.value)}
            placeholder="筛选联赛、国家或赛季"
            type="search"
            value={filterText}
          />
          <select
            onChange={(event) =>
              onSortChange(event.target.value as "coverage_desc" | "coverage_asc" | "unmatched_desc")
            }
            value={sortBy}
          >
            <option value="coverage_desc">覆盖率从高到低</option>
            <option value="coverage_asc">覆盖率从低到高</option>
            <option value="unmatched_desc">未匹配从多到少</option>
          </select>
        </div>
        <LeagueCoverageTable leagues={data.leagues} filterText={filterText} sortBy={sortBy} />
      </Panel>
    </>
  );
}

function WorkersView({ data }: { data: DashboardData }) {
  return (
    <section className="single-column">
      <Panel title="后台回填 Worker">
        <WorkerStatusTable workers={data.workers} />
      </Panel>
      <Panel title="操作提示">
        <div className="note-list">
          <p>当前页面只展示状态，不负责启动、停止或巡检 worker。</p>
          <p>worker 巡检、未匹配别名矫正和回填收尾继续由另一条对话处理。</p>
        </div>
      </Panel>
    </section>
  );
}

function UnmatchedView({ data }: { data: DashboardData }) {
  return (
    <section className="single-column">
      <Panel title="待处理未匹配比赛">
        <UnmatchedTable matches={data.unmatched} />
      </Panel>
    </section>
  );
}

function DisplayNamesView({
  data,
  doneKeys,
  draftNames,
  filterText,
  isSaving,
  onDraftNamesChange,
  onFilterTextChange,
  onMarkDone,
  onSaveDrafts,
  onStatusFilterChange,
  onWorkspaceChange,
  statusFilter,
  workspace,
  workspaceError,
  workspaceMessage
}: {
  data: DashboardData;
  doneKeys: Set<string>;
  draftNames: Record<string, string>;
  filterText: string;
  isSaving: boolean;
  onDraftNamesChange: (draftNames: Record<string, string>) => void;
  onFilterTextChange: (value: string) => void;
  onMarkDone: (leagueId: number, season: number) => void;
  onSaveDrafts: () => void;
  onStatusFilterChange: (value: DisplayNameStatusFilter) => void;
  onWorkspaceChange: (leagueId: number, season: number) => void;
  statusFilter: DisplayNameStatusFilter;
  workspace: TeamDisplayNameWorkspace | null;
  workspaceError: string | null;
  workspaceMessage: string | null;
}) {
  const workspaceOptions = buildTeamDisplayWorkspaceOptions(data.leagues, doneKeys);
  const visibleTeams = filterTeamDisplayRows(workspace?.teams ?? [], {
    draftNames,
    filterText,
    statusFilter
  });
  const actionState = getDisplayNameActionState({
    draftNames,
    isSaving,
    isTranslationDone: workspace?.is_translation_done ?? false
  });

  return (
    <section className="single-column">
      <Panel title="球队中文名校验">
        <div className="table-toolbar">
          <select
            onChange={(event) => {
              const [leagueId, season] = event.target.value.split("-").map(Number);
              onWorkspaceChange(leagueId, season);
            }}
            value={workspace ? `${workspace.league_id}-${workspace.season}` : ""}
          >
            {workspaceOptions.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            onChange={(event) => onFilterTextChange(event.target.value)}
            placeholder="筛选球队英文名或当前中文名"
            type="search"
            value={filterText}
          />
          <select
            onChange={(event) => onStatusFilterChange(event.target.value as DisplayNameStatusFilter)}
            value={statusFilter}
          >
            <option value="all">全部球队</option>
            <option value="missing">只看未翻译</option>
            <option value="changed">只看已修改</option>
          </select>
        </div>
        {workspaceError && <div className="inline-warning">{workspaceError}</div>}
        {workspaceMessage && <div className="inline-success">{workspaceMessage}</div>}
        {workspace && (
          <div className="match-heading">
            <strong>
              {workspace.league_display_name ?? workspace.league_name} · {workspace.season}
            </strong>
            <span>{workspace.is_translation_done ? "已完成校验" : `${workspace.teams.length} 支球队`}</span>
          </div>
        )}
        {workspace && (
          <div className="inline-actions">
            <button disabled={!actionState.canSave} onClick={onSaveDrafts} type="button">
              {actionState.saveLabel}
            </button>
            <button
              disabled={!actionState.canMarkDone}
              onClick={() => onMarkDone(workspace.league_id, workspace.season)}
              type="button"
            >
              {actionState.markDoneLabel}
            </button>
            {hasMeaningfulDrafts(draftNames) && <span>有未保存草稿</span>}
          </div>
        )}
        <TeamDisplayNameEditor
          draftNames={draftNames}
          onDraftNamesChange={onDraftNamesChange}
          teams={visibleTeams}
        />
      </Panel>
    </section>
  );
}

function saveCurrentTeamDisplayDrafts(draftNames: Record<string, string>) {
  const teams = Object.fromEntries(
    Object.entries(draftNames)
      .map(([teamName, displayName]) => [teamName, displayName.trim()])
      .filter(([, displayName]) => displayName.length > 0)
  );
  return saveTeamDisplayNames(teams).then((result) => result.saved_count);
}

function OddsView({
  data,
  errorText,
  oddsTrends,
  selectedMatchId,
  onMatchChange
}: {
  data: DashboardData;
  errorText: string | null;
  oddsTrends: MatchOddsTrends;
  selectedMatchId: number;
  onMatchChange: (matchId: number) => void;
}) {
  return (
    <section className="single-column">
      <Panel title="赔率走势预览">
        <div className="table-toolbar">
          <select
            onChange={(event) => onMatchChange(Number(event.target.value))}
            value={selectedMatchId}
          >
            {data.matchesWithOdds.map((match) => (
              <option key={match.match_id} value={match.match_id}>
                {match.league_display_name ?? match.league_name}{" "}
                {match.home_team_display_name ?? match.home_team_name} vs{" "}
                {match.away_team_display_name ?? match.away_team_name} ·{" "}
                {formatShortDateTime(match.kickoff_time)} · {match.snapshot_count} 快照
              </option>
            ))}
          </select>
        </div>
        {errorText && <div className="inline-warning">{errorText}</div>}
        <OddsTrendPanel trends={oddsTrends} />
      </Panel>
    </section>
  );
}

function formatShortDateTime(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function RecordsView({ data }: { data: DashboardData }) {
  return (
    <section className="single-column">
      <Panel title="推荐记录">
        <RecommendationRecordTable records={data.recommendationRecords} />
      </Panel>
    </section>
  );
}

function SummaryMetrics({ data }: { data: DashboardData }) {
  return (
    <section className="metrics">
      <MetricCard label="比赛总数" value={data.summary.total_matches.toLocaleString()} />
      <MetricCard label="完赛场次" value={data.summary.finished_matches.toLocaleString()} />
      <MetricCard
        label="有赔率场次"
        value={data.summary.matches_with_historical_odds.toLocaleString()}
      />
      <MetricCard label="赔率快照" value={data.summary.historical_odds_snapshots.toLocaleString()} />
      <MetricCard
        label="未匹配"
        value={data.summary.unmatched_matches.toLocaleString()}
        tone="warning"
      />
    </section>
  );
}
