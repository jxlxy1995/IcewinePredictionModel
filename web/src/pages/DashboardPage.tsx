import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  BrainCircuit,
  CircleAlert,
  ClipboardList,
  Database,
  FileCheck2,
  FlaskConical,
  Languages,
  ListChecks,
  Play,
  ScrollText,
  Search,
  Radio
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  loadDashboardData,
  loadMatchDetail,
  loadMatchListWorkspace,
  loadMatchOddsTrend,
  loadMatchSyncRunDetail,
  loadOddspapiBackfillAudit,
  loadPaperRecommendationWorkspace,
  loadTrainingWorkspace,
  startTrainingFullRefresh,
  markTeamDisplayNameWorkspaceDone,
  editPaperRecord,
  recordPaperCandidate,
  runTrainingWorkflowAction,
  saveTeamDisplayNames,
  settlePaperRecords,
  syncFilteredMatchListFixturesResults,
  syncFilteredMatchListOdds,
  syncSingleMatchFixturesResults,
  syncSingleMatchOdds,
  voidPaperRecord,
  loadTeamDisplayNameWorkspace
} from "../apiClient";
import { LeagueCoverageTable } from "../components/LeagueCoverageTable";
import { MetricCard } from "../components/MetricCard";
import { MatchListTable } from "../components/MatchListTable";
import { OddsTrendPanel } from "../components/OddsTrendPanel";
import { PaperCandidateTable, PaperRecordTable } from "../components/PaperRecommendationTables";
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
import {
  buildTrainingRunCards,
  buildTrainingWorkspaceCards,
  countTrainingQualityIssues,
  formatMarketType,
  formatTrainingRunStatus,
  formatTrainingRunStep,
  listTrainingMarketRows
} from "../modelTrainingWorkspace";
import {
  buildOddspapiAuditSummaryCards,
  listOddspapiLeagueAuditRows
} from "../oddspapiBackfillAuditWorkspace";
import {
  buildRecommendationRecordGroups,
  buildRecommendationRecordSummary
} from "../recordReportWorkspace";
import {
  buildPaperRecordGroups,
  buildPaperSummaryCards
} from "../paperRecommendationWorkspace";
import {
  buildMatchFreshnessCards,
  buildMatchSyncSummary,
  defaultMatchListDateRange,
  formatMatchStatus,
  summarizeMatchDetail
} from "../matchListWorkspace";
import { WorkerStatusTable } from "../components/WorkerStatusTable";
import { mockDashboardData } from "../mockData";
import type { DisplayNameStatusFilter } from "../displayNameWorkspace";
import type {
  DashboardData,
  MatchDetail,
  MatchListMatch,
  MatchSyncReport,
  MatchSyncRunDetail,
  MatchOddsTrends,
  PaperCandidate,
  PaperRecord,
  TeamDisplayNameWorkspace
} from "../types";

type ViewKey =
  | "overview"
  | "matchList"
  | "coverage"
  | "workers"
  | "oddspapiAudit"
  | "unmatched"
  | "displayNames"
  | "models"
  | "paperTracking"
  | "odds"
  | "records";

type NavItem = {
  key: ViewKey;
  label: string;
  icon: LucideIcon;
};

type MatchListFilterState = {
  end_time: string;
  league_name: string;
  odds_filter: string[];
  search: string;
  start_time: string;
  status_filter: string;
};

type PaperFilterState = {
  end_time: string;
  start_time: string;
};

const matchOddsStatusOptions = [
  { key: "none", label: "无赔率" },
  { key: "early", label: "早盘" },
  { key: "near", label: "近盘" },
  { key: "close", label: "临盘" },
  { key: "pending_fill", label: "待回填" },
  { key: "filled", label: "已回填" }
];

export const initialDashboardView: ViewKey = "matchList";

export const dashboardNavItems: NavItem[] = [
  { key: "matchList", label: "比赛列表", icon: Search },
  { key: "displayNames", label: "中文名", icon: Languages },
  { key: "models", label: "模型训练", icon: BrainCircuit },
  { key: "paperTracking", label: "纸面跟踪", icon: ScrollText },
  { key: "records", label: "推荐记录", icon: ListChecks }
];

const viewText: Record<ViewKey, { title: string; subtitle: string }> = {
  overview: {
    title: "控制台总览",
    subtitle: "本地数据回填、赔率覆盖和模型推荐的工作台"
  },
  matchList: {
    title: "比赛列表",
    subtitle: "同步近期数据，按时间、联赛、状态和赔率浏览本地比赛"
  },
  coverage: {
    title: "联赛覆盖率",
    subtitle: "按联赛和赛季检查历史赔率快照覆盖情况"
  },
  workers: {
    title: "Worker 状态",
    subtitle: "查看后台回填进程、批次参数和日志路径"
  },
  oddspapiAudit: {
    title: "OddsPapi 回填审计",
    subtitle: "查看后台回填进度、联赛覆盖和匹配失败分布"
  },
  unmatched: {
    title: "未匹配比赛",
    subtitle: "集中处理外部数据源队名差异和匹配失败记录"
  },
  displayNames: {
    title: "中文名维护",
    subtitle: "按联赛和赛季检查缺失中文显示名的球队"
  },
  models: {
    title: "模型训练",
    subtitle: "生成 baseline 训练集、执行 QA，并用 close-market 基准做 sanity check"
  },
  paperTracking: {
    title: "纸面跟踪",
    subtitle: "观察期候选、人工记录、赛后结算和策略复盘"
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
  const [activeView, setActiveView] = useState<ViewKey>(initialDashboardView);
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
  const [trainingAction, setTrainingAction] = useState<string | null>(null);
  const [trainingMessage, setTrainingMessage] = useState<string | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [paperAction, setPaperAction] = useState<string | null>(null);
  const [paperMessage, setPaperMessage] = useState<string | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);
  const [paperFilters, setPaperFilters] = useState<PaperFilterState>({
    end_time: "",
    start_time: ""
  });
  const [matchListAction, setMatchListAction] = useState<string | null>(null);
  const [matchListMessage, setMatchListMessage] = useState<string | null>(null);
  const [matchListError, setMatchListError] = useState<string | null>(null);
  const [matchListSyncReport, setMatchListSyncReport] = useState<MatchSyncReport | null>(null);
  const [matchListSyncRunDetail, setMatchListSyncRunDetail] = useState<MatchSyncRunDetail | null>(null);
  const [matchDetailOddsTrends, setMatchDetailOddsTrends] = useState<MatchOddsTrends | null>(null);
  const [matchDetailOddsError, setMatchDetailOddsError] = useState<string | null>(null);
  const [matchListFilters, setMatchListFilters] = useState<MatchListFilterState>({
    ...defaultMatchListDateRange(),
    league_name: "",
    odds_filter: [],
    search: "",
    status_filter: "all"
  });
  const [selectedMatchDetail, setSelectedMatchDetail] = useState<MatchDetail | null>(null);
  const [loadedLazyViews, setLoadedLazyViews] = useState<Set<ViewKey>>(new Set());

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
      setIsLoading(false);
    });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (isLoading || loadedLazyViews.has(activeView)) {
      return;
    }
    setLoadedLazyViews(new Set([...loadedLazyViews, activeView]));
    if (activeView === "matchList") {
      setMatchListAction("refresh");
      refreshMatchListWorkspace(setData, matchListFilters)
        .catch((error) => setMatchListError(formatActionError("刷新比赛列表失败", error)))
        .finally(() => setMatchListAction(null));
    }
    if (activeView === "oddspapiAudit") {
      loadOddspapiBackfillAudit().then((audit) => {
        setData((current) => ({ ...current, oddspapiBackfillAudit: audit }));
      });
    }
    if (activeView === "models") {
      setTrainingAction("refresh");
      loadTrainingWorkspace()
        .then((workspace) => {
          setData((current) => ({ ...current, trainingWorkspace: workspace }));
        })
        .catch(() => setTrainingError("读取训练工作台失败"))
        .finally(() => setTrainingAction(null));
    }
    if (activeView === "paperTracking") {
      setPaperAction("refresh");
      refreshPaperWorkspace(setData, paperFilters)
        .catch(() => setPaperError("刷新纸面跟踪失败"))
        .finally(() => setPaperAction(null));
    }
    if (activeView === "displayNames") {
      const firstLeague = data.leagues[0];
      if (firstLeague?.season != null) {
        loadTeamDisplayNameWorkspace(firstLeague.league_id, firstLeague.season)
          .then(setTeamDisplayWorkspace)
          .catch(() => setDisplayWorkspaceError("读取球队中文名维护列表失败"));
      }
    }
    if (activeView === "odds") {
      const firstMatchId = data.matchesWithOdds[0]?.match_id;
      if (firstMatchId) {
        setSelectedOddsMatchId(firstMatchId);
        loadMatchOddsTrend(firstMatchId)
          .then(setOddsTrends)
          .catch(() => setOddsTrendError("读取首场赔率走势失败"));
      }
    }
  }, [activeView, data.leagues, data.matchesWithOdds, isLoading, loadedLazyViews, matchListFilters]);

  useEffect(() => {
    if (activeView !== "models" || data.trainingWorkspace.latest_run?.status !== "running") {
      return;
    }
    const intervalId = window.setInterval(() => {
      loadTrainingWorkspace()
        .then((workspace) => {
          setData((current) => ({ ...current, trainingWorkspace: workspace }));
          if (workspace.latest_run?.status === "success") {
            setTrainingMessage("训练与模型报告刷新已完成");
          }
          if (workspace.latest_run?.status === "failed") {
            setTrainingError("训练与模型报告刷新失败");
          }
        })
        .catch(() => setTrainingError("刷新训练运行状态失败"));
    }, 3000);
    return () => window.clearInterval(intervalId);
  }, [activeView, data.trainingWorkspace.latest_run?.status]);

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
          {dashboardNavItems.map((item) => {
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
        {activeView === "matchList" && (
          <FilteredMatchListView
            actionInFlight={matchListAction}
            data={data}
            detail={selectedMatchDetail}
            detailOddsError={matchDetailOddsError}
            detailOddsTrends={matchDetailOddsTrends}
            errorText={matchListError}
            filters={matchListFilters}
            messageText={matchListMessage}
            syncReport={matchListSyncReport}
            syncRunDetail={matchListSyncRunDetail}
            onBackToList={() => {
              setSelectedMatchDetail(null);
              setMatchDetailOddsTrends(null);
              setMatchDetailOddsError(null);
            }}
            onFiltersChange={(nextFilters) => {
              const merged = { ...matchListFilters, ...nextFilters };
              setMatchListFilters(merged);
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              refreshMatchListWorkspace(setData, merged).catch((error) =>
                setMatchListError(formatActionError("刷新比赛列表失败", error))
              );
            }}
            onLoadSyncRunDetail={(runId) => {
              setMatchListAction(`sync-detail-${runId}`);
              setMatchListError(null);
              loadMatchSyncRunDetail(runId)
                .then(setMatchListSyncRunDetail)
                .catch((error) => setMatchListError(formatActionError("读取同步诊断明细失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onOpenMatch={(match) => {
              setMatchListAction(`detail-${match.match_id}`);
              setMatchListError(null);
              setMatchDetailOddsTrends(null);
              setMatchDetailOddsError(null);
              loadMatchDetail(match.match_id)
                .then((detail) => {
                  setSelectedMatchDetail(detail);
                  if (!detail.has_odds) {
                    return null;
                  }
                  return loadMatchOddsTrend(match.match_id)
                    .then(setMatchDetailOddsTrends)
                    .catch(() => setMatchDetailOddsError("读取赔率走势失败，请稍后重试"));
                })
                .catch((error) => setMatchListError(formatActionError("读取比赛详情失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onSyncFixturesResults={() => {
              setMatchListAction("sync-fixtures");
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncFilteredMatchListFixturesResults(matchListFilters)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("赛程/赛果同步完成"))
                .catch((error) => setMatchListError(formatActionError("赛程/赛果同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onSyncMatchFixturesResults={(match) => {
              setMatchListAction(`sync-fixtures-${match.match_id}`);
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncSingleMatchFixturesResults(match.match_id)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("赛程/赛果同步完成"))
                .catch((error) => setMatchListError(formatActionError("赛程/赛果同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onSyncOdds={() => {
              setMatchListAction("sync-odds");
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncFilteredMatchListOdds(matchListFilters)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("赔率同步完成"))
                .catch((error) => setMatchListError(formatActionError("赔率同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onSyncMatchOdds={(match) => {
              setMatchListAction(`sync-odds-${match.match_id}`);
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncSingleMatchOdds(match.match_id)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("赔率同步完成"))
                .catch((error) => setMatchListError(formatActionError("赔率同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
          />
        )}
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
        {activeView === "oddspapiAudit" && <OddspapiAuditView data={data} />}
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
        {activeView === "models" && (
          <ModelTrainingView
            actionInFlight={trainingAction}
            data={data}
            errorText={trainingError}
            messageText={trainingMessage}
            onFullRefresh={() => {
              setTrainingAction("full-refresh");
              setTrainingError(null);
              setTrainingMessage(null);
              startTrainingFullRefresh()
                .then((run) => {
                  setData((current) => ({
                    ...current,
                    trainingWorkspace: { ...current.trainingWorkspace, latest_run: run }
                  }));
                  setTrainingMessage("训练与模型报告刷新已开始");
                })
                .catch(() => setTrainingError("训练与模型报告刷新启动失败"))
                .finally(() => setTrainingAction(null));
            }}
            onRunAction={(action) => {
              setTrainingAction(action);
              setTrainingError(null);
              setTrainingMessage(null);
              runTrainingWorkflowAction(action)
                .then((workspace) => {
                  setData((current) => ({ ...current, trainingWorkspace: workspace }));
                  setTrainingMessage("训练工作流已更新");
                })
                .catch(() => setTrainingError("训练工作流执行失败"))
                .finally(() => setTrainingAction(null));
            }}
          />
        )}
        {activeView === "paperTracking" && (
          <PaperTrackingView
            actionInFlight={paperAction}
            data={data}
            errorText={paperError}
            filters={paperFilters}
            messageText={paperMessage}
            onBatchRecord={(candidates) => {
              setPaperAction("batch-record");
              setPaperError(null);
              setPaperMessage(null);
              Promise.all(
                candidates.map((candidate) =>
                  recordPaperCandidate(candidate.match_id, candidate.strategy_key, paperFilters)
                )
              )
                .then(() => refreshPaperWorkspace(setData, paperFilters))
                .then(() => setPaperMessage(`已记录 ${candidates.length} 条纸面观察`))
                .catch(() => setPaperError("批量记录纸面观察失败"))
                .finally(() => setPaperAction(null));
            }}
            onEdit={(record, payload) => {
              setPaperAction(`edit-${record.id}`);
              setPaperError(null);
              setPaperMessage(null);
              editPaperRecord(record.id, payload)
                .then(() => refreshPaperWorkspace(setData, paperFilters))
                .then(() => setPaperMessage("纸面记录已更新"))
                .catch(() => setPaperError("编辑纸面记录失败"))
                .finally(() => setPaperAction(null));
            }}
            onRecord={(candidate) => {
              setPaperAction(`record-${candidate.match_id}`);
              setPaperError(null);
              setPaperMessage(null);
              recordPaperCandidate(candidate.match_id, candidate.strategy_key, paperFilters)
                .then(() => refreshPaperWorkspace(setData, paperFilters))
                .then(() => setPaperMessage("已记录纸面观察"))
                .catch(() => setPaperError("记录纸面观察失败"))
                .finally(() => setPaperAction(null));
            }}
            onFiltersChange={(filters) => {
              setPaperFilters((current) => ({ ...current, ...filters }));
            }}
            onRefresh={() => {
              setPaperAction("refresh");
              setPaperError(null);
              setPaperMessage(null);
              refreshPaperWorkspace(setData, paperFilters)
                .then(() => setPaperMessage("纸面跟踪已刷新"))
                .catch(() => setPaperError("刷新纸面跟踪失败"))
                .finally(() => setPaperAction(null));
            }}
            onSettle={() => {
              setPaperAction("settle");
              setPaperError(null);
              setPaperMessage(null);
              settlePaperRecords()
                .then(() => refreshPaperWorkspace(setData, paperFilters))
                .then(() => setPaperMessage("已结算可结算纸面记录"))
                .catch(() => setPaperError("结算纸面记录失败"))
                .finally(() => setPaperAction(null));
            }}
            onVoid={(record) => {
              setPaperAction(`void-${record.id}`);
              setPaperError(null);
              setPaperMessage(null);
              voidPaperRecord(record.id)
                .then(() => refreshPaperWorkspace(setData, paperFilters))
                .then(() => setPaperMessage("纸面记录已作废"))
                .catch(() => setPaperError("作废纸面记录失败"))
                .finally(() => setPaperAction(null));
            }}
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

function MatchListView({
  actionInFlight,
  data,
  detail,
  errorText,
  filters,
  fixturesSyncDays,
  messageText,
  oddsSyncDays,
  onBackToList,
  onFiltersChange,
  onFixturesSyncDaysChange,
  onOddsSyncDaysChange,
  onOpenMatch,
  onSyncFixturesResults,
  onSyncOdds
}: {
  actionInFlight: string | null;
  data: DashboardData;
  detail: MatchDetail | null;
  errorText: string | null;
  filters: {
    end_time: string;
    league_name: string;
    odds_filter: string[];
    search: string;
    start_time: string;
    status_filter: string;
  };
  fixturesSyncDays: number;
  messageText: string | null;
  oddsSyncDays: number;
  onBackToList: () => void;
  onFiltersChange: (filters: Partial<MatchListFilterState>) => void;
  onFixturesSyncDaysChange: (days: number) => void;
  onOddsSyncDaysChange: (days: number) => void;
  onOpenMatch: (match: MatchListMatch) => void;
  onSyncFixturesResults: () => void;
  onSyncOdds: () => void;
}) {
  if (detail) {
    return (
      <MatchDetailView
        detail={detail}
        oddsError={null}
        oddsTrends={null}
        onBack={onBackToList}
      />
    );
  }
  const workspace = data.matchList;
  const freshnessCards = buildMatchFreshnessCards(workspace);
  const isBusy = actionInFlight !== null;

  return (
    <section className="single-column">
      <section className="match-sync-strip">
        {freshnessCards.slice(0, 2).map((card) => (
          <div className="sync-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <small>{card.meta}</small>
          </div>
        ))}
        <div className="sync-action">
          <label>
            天数
            <input
              min={1}
              onChange={(event) => onFixturesSyncDaysChange(Number(event.target.value))}
              type="number"
              value={fixturesSyncDays}
            />
          </label>
          <button disabled={isBusy} onClick={onSyncFixturesResults} type="button">
            同步赛程/赛果
          </button>
        </div>
        <div className="sync-action">
          <label>
            天数
            <input
              min={1}
              onChange={(event) => onOddsSyncDaysChange(Number(event.target.value))}
              type="number"
              value={oddsSyncDays}
            />
          </label>
          <button disabled={isBusy} onClick={onSyncOdds} type="button">
            同步赔率
          </button>
        </div>
      </section>
      <section className="match-secondary-freshness">
        {freshnessCards.slice(2).map((card) => (
          <span key={card.label}>
            {card.label}: <strong>{card.value}</strong>
          </span>
        ))}
        {actionInFlight && <span>正在执行 {formatMatchListAction(actionInFlight)}</span>}
        {messageText && <span className="success-text">{messageText}</span>}
        {errorText && <span className="error-text">{errorText}</span>}
      </section>
      <Panel title="筛选">
        <div className="match-filter-row">
          <label>
            <span>开始时间</span>
            <input
              onChange={(event) => onFiltersChange({ start_time: event.target.value })}
              type="datetime-local"
              value={filters.start_time}
            />
          </label>
          <label>
            <span>结束时间</span>
            <input
              onChange={(event) => onFiltersChange({ end_time: event.target.value })}
              type="datetime-local"
              value={filters.end_time}
            />
          </label>
          <select
            onChange={(event) => onFiltersChange({ league_name: event.target.value })}
            value={filters.league_name}
          >
            <option value="">全部联赛</option>
            {workspace.leagues.map((league) => (
              <option key={league.name} value={league.name}>
                {league.display_name}
              </option>
            ))}
          </select>
          <select
            onChange={(event) => onFiltersChange({ status_filter: event.target.value })}
            value={filters.status_filter}
          >
            <option value="all">全部状态</option>
            <option value="not_started">未开赛</option>
            <option value="live">进行中</option>
            <option value="finished">已完赛</option>
          </select>
          <OddsStatusFilter
            selected={filters.odds_filter}
            onChange={(odds_filter) => onFiltersChange({ odds_filter })}
          />
          <input
            onChange={(event) => onFiltersChange({ search: event.target.value })}
            placeholder="搜索球队"
            value={filters.search}
          />
        </div>
      </Panel>
      <Panel title={`比赛列表 · ${workspace.total_matches.toLocaleString()} 场`}>
        <MatchListTable onOpenMatch={onOpenMatch} workspace={workspace} />
      </Panel>
    </section>
  );
}

function FilteredMatchListView({
  actionInFlight,
  data,
  detail,
  detailOddsError,
  detailOddsTrends,
  errorText,
  filters,
  messageText,
  syncReport,
  syncRunDetail,
  onBackToList,
  onFiltersChange,
  onLoadSyncRunDetail,
  onOpenMatch,
  onSyncFixturesResults,
  onSyncMatchFixturesResults,
  onSyncMatchOdds,
  onSyncOdds
}: {
  actionInFlight: string | null;
  data: DashboardData;
  detail: MatchDetail | null;
  detailOddsError: string | null;
  detailOddsTrends: MatchOddsTrends | null;
  errorText: string | null;
  filters: MatchListFilterState;
  messageText: string | null;
  syncReport: MatchSyncReport | null;
  syncRunDetail: MatchSyncRunDetail | null;
  onBackToList: () => void;
  onFiltersChange: (filters: Partial<MatchListFilterState>) => void;
  onLoadSyncRunDetail: (runId: number) => void;
  onOpenMatch: (match: MatchListMatch) => void;
  onSyncFixturesResults: () => void;
  onSyncMatchFixturesResults: (match: MatchListMatch) => void;
  onSyncMatchOdds: (match: MatchListMatch) => void;
  onSyncOdds: () => void;
}) {
  if (detail) {
    return (
      <MatchDetailView
        detail={detail}
        oddsError={detailOddsError}
        oddsTrends={detailOddsTrends}
        onBack={onBackToList}
      />
    );
  }
  const workspace = data.matchList;
  const freshnessCards = buildMatchFreshnessCards(workspace);
  const isBusy = actionInFlight !== null;

  return (
    <section className="single-column">
      <section className="match-sync-strip">
        {freshnessCards.slice(0, 2).map((card) => (
          <div className="sync-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <small>按当前筛选</small>
          </div>
        ))}
        <div className="sync-action">
          <button disabled={isBusy} onClick={onSyncFixturesResults} type="button">
            同步赛程/赛果
          </button>
        </div>
        <div className="sync-action">
          <button disabled={isBusy} onClick={onSyncOdds} type="button">
            同步赔率
          </button>
        </div>
      </section>
      <section className="match-secondary-freshness">
        {freshnessCards.slice(2).map((card) => (
          <span key={card.label}>
            {card.label}: <strong>{card.value}</strong>
          </span>
        ))}
        {actionInFlight && <span>正在执行 {formatMatchListAction(actionInFlight)}</span>}
        {messageText && <span className="success-text">{messageText}</span>}
        {errorText && <span className="error-text">{errorText}</span>}
      </section>
      {syncRunDetail && (
        <MatchSyncDiagnosticsPanel
          detail={syncRunDetail}
          isBusy={actionInFlight === `sync-detail-${syncRunDetail.sync_run.id}`}
          onReload={onLoadSyncRunDetail}
        />
      )}
      {syncReport && <MatchSyncResultPanel report={syncReport} />}
      <Panel title="筛选">
        <div className="match-filter-row">
          <label>
            <span>开始时间</span>
            <input
              onChange={(event) => onFiltersChange({ start_time: event.target.value })}
              type="datetime-local"
              value={filters.start_time}
            />
          </label>
          <label>
            <span>结束时间</span>
            <input
              onChange={(event) => onFiltersChange({ end_time: event.target.value })}
              type="datetime-local"
              value={filters.end_time}
            />
          </label>
          <select
            onChange={(event) => onFiltersChange({ league_name: event.target.value })}
            value={filters.league_name}
          >
            <option value="">全部联赛</option>
            {workspace.leagues.map((league) => (
              <option key={league.name} value={league.name}>
                {league.display_name}
              </option>
            ))}
          </select>
          <select
            onChange={(event) => onFiltersChange({ status_filter: event.target.value })}
            value={filters.status_filter}
          >
            <option value="all">全部状态</option>
            <option value="not_started">未开赛</option>
            <option value="live">进行中</option>
            <option value="finished">已完赛</option>
          </select>
          <OddsStatusFilter
            selected={filters.odds_filter}
            onChange={(odds_filter) => onFiltersChange({ odds_filter })}
          />
          <input
            onChange={(event) => onFiltersChange({ search: event.target.value })}
            placeholder="搜索球队"
            value={filters.search}
          />
        </div>
      </Panel>
      <Panel title={`比赛列表 · ${workspace.total_matches.toLocaleString()} 场`}>
        <MatchListTable
          isBusy={isBusy}
          onOpenMatch={onOpenMatch}
          onSyncFixturesResults={onSyncMatchFixturesResults}
          onSyncOdds={onSyncMatchOdds}
          workspace={workspace}
        />
      </Panel>
    </section>
  );
}

function MatchSyncResultPanel({ report }: { report: MatchSyncReport }) {
  const summary = buildMatchSyncSummary(report);
  return (
    <Panel title={summary.title}>
      <div className="sync-result-summary">{summary.line}</div>
      <div className="sync-result-groups">
        <MatchSyncResultGroup label="成功" items={report.success} />
        <MatchSyncResultGroup label="失败" items={report.failed} />
        <MatchSyncResultGroup label="跳过" items={report.skipped} />
      </div>
    </Panel>
  );
}

function MatchSyncDiagnosticsPanel({
  detail,
  isBusy,
  onReload
}: {
  detail: MatchSyncRunDetail;
  isBusy: boolean;
  onReload: (runId: number) => void;
}) {
  return (
    <Panel title={`最近同步诊断 · #${detail.sync_run.id}`}>
      <div className="sync-result-summary">
        {buildMatchSyncSummary(detail.report).line}
        <button
          className="inline-action compact-action"
          disabled={isBusy}
          onClick={() => onReload(detail.sync_run.id)}
          type="button"
        >
          {isBusy ? "读取中" : "刷新明细"}
        </button>
      </div>
      <div className="sync-result-groups">
        <MatchSyncResultGroup label="失败诊断" items={detail.report.failed} />
        <MatchSyncResultGroup label="成功诊断" items={detail.report.success} />
        <MatchSyncResultGroup label="跳过诊断" items={detail.report.skipped} />
      </div>
    </Panel>
  );
}

function MatchSyncResultGroup({
  items,
  label
}: {
  items: MatchSyncReport["success"];
  label: string;
}) {
  return (
    <details className="sync-result-group">
      <summary>
        {label} <strong>{items.length}</strong>
      </summary>
      {items.length === 0 ? (
        <div className="empty-state compact">暂无明细</div>
      ) : (
        <div className="sync-result-list">
          {items.map((item) => (
            <div className="sync-result-item" key={`${label}-${item.match_id}`}>
              <strong>
                {item.league_display_name ?? item.league_name} {item.fixture}
              </strong>
              <span>{item.kickoff_time}</span>
              {item.message && <small>{item.message}</small>}
              {(item.diagnostic_status || item.diagnostic_error || item.source_fixture_id || item.snapshot_count > 0) && (
                <small>
                  诊断: {item.diagnostic_status ?? "-"} · 快照 {item.snapshot_count}
                  {item.source_fixture_id ? ` · fixture ${item.source_fixture_id}` : ""}
                  {item.diagnostic_error ? ` · ${item.diagnostic_error}` : ""}
                </small>
              )}
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

function MatchDetailView({
  detail,
  oddsError,
  oddsTrends,
  onBack
}: {
  detail: MatchDetail;
  oddsError: string | null;
  oddsTrends: MatchOddsTrends | null;
  onBack: () => void;
}) {
  const summary = summarizeMatchDetail(detail);
  return (
    <section className="single-column">
      <button className="inline-action" onClick={onBack} type="button">
        返回比赛列表
      </button>
      <Panel title={summary.fixture}>
        <div className="match-detail-header">
          <TeamBadge logoUrl={detail.home_team_logo_url} name={detail.home_team_display_name ?? detail.home_team_name} />
          <div className="match-detail-score">
            <strong>
              {detail.home_score == null || detail.away_score == null
                ? "-"
                : `${detail.home_score}-${detail.away_score}`}
            </strong>
            <span>{formatMatchStatus(detail.status_group)}</span>
            <small>{detail.kickoff_time}</small>
          </div>
          <TeamBadge logoUrl={detail.away_team_logo_url} name={detail.away_team_display_name ?? detail.away_team_name} />
        </div>
      </Panel>
      <section className="grid">
        <Panel title="球队数据">
          <div className="empty-state">{summary.teamData}</div>
        </Panel>
        <Panel title="推荐摘要">
          <div className="record-placeholder">
            <div>{detail.paper_recommendation_summary.label}</div>
            <div>{detail.formal_recommendation_summary.label}</div>
          </div>
        </Panel>
      </section>
      <Panel title="赔率摘要">
        <div className="odds-summary-grid">
          <div>
            <span>亚盘</span>
            <strong>{detail.odds_summary.asian_handicap ?? "-"}</strong>
          </div>
          <div>
            <span>大小球</span>
            <strong>{detail.odds_summary.total_goals ?? "-"}</strong>
          </div>
          <div>
            <span>胜平负</span>
            <strong>{detail.odds_summary.match_winner ?? "-"}</strong>
          </div>
        </div>
      </Panel>
      {detail.has_odds && (
        <Panel title="赔率走势">
          {oddsError && <div className="inline-warning">{oddsError}</div>}
          {oddsTrends ? (
            <OddsTrendPanel compactHeader trends={oddsTrends} />
          ) : (
            <div className="empty-state">正在读取赔率走势</div>
          )}
        </Panel>
      )}
    </section>
  );
}

function TeamBadge({ logoUrl, name }: { logoUrl?: string | null; name: string }) {
  return (
    <div className="team-badge">
      {logoUrl ? <img alt="" src={logoUrl} /> : <span className="team-logo-placeholder large" />}
      <strong>{name}</strong>
    </div>
  );
}

function OddsStatusFilter({
  onChange,
  selected
}: {
  onChange: (selected: string[]) => void;
  selected: string[];
}) {
  const selectedSet = new Set(selected);
  return (
    <div className="odds-status-filter" aria-label="赔率状态">
      {matchOddsStatusOptions.map((option) => (
        <label className={selectedSet.has(option.key) ? "selected" : ""} key={option.key}>
          <input
            checked={selectedSet.has(option.key)}
            onChange={(event) => {
              const next = event.target.checked
                ? [...selected, option.key]
                : selected.filter((key) => key !== option.key);
              onChange(next);
            }}
            type="checkbox"
          />
          {option.label}
        </label>
      ))}
    </div>
  );
}

function refreshMatchListWorkspace(
  setData: React.Dispatch<React.SetStateAction<DashboardData>>,
  filters: {
    end_time?: string;
    league_name?: string | null;
    odds_filter?: string[];
    search?: string | null;
    start_time?: string;
    status_filter?: string;
  }
): Promise<void> {
  return loadMatchListWorkspace(filters).then((workspace) => {
    setData((current) => ({ ...current, matchList: workspace }));
  });
}

function formatActionError(prefix: string, error: unknown): string {
  if (error instanceof Error && error.message) {
    return `${prefix}: ${error.message}`;
  }
  return prefix;
}

function formatMatchListAction(action: string) {
  if (action === "sync-fixtures") {
    return "同步赛程/赛果";
  }
  if (action === "sync-odds") {
    return "同步赔率";
  }
  if (action.startsWith("detail-")) {
    return "读取详情";
  }
  return action;
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

function OddspapiAuditView({ data }: { data: DashboardData }) {
  const audit = data.oddspapiBackfillAudit;
  const summaryCards = buildOddspapiAuditSummaryCards(audit);
  const leagueRows = listOddspapiLeagueAuditRows(audit);
  const progress = audit.worker_progress;

  return (
    <section className="single-column">
      <section className="metrics compact-metrics">
        {summaryCards.map((card) => (
          <MetricCard key={card.label} label={card.label} value={card.value} />
        ))}
      </section>
      <section className="grid">
        <Panel title="Worker 进度">
          {progress ? (
            <div className="audit-progress">
              <div className="match-heading">
                <strong>{progress.current_league_display_name ?? progress.current_league_name ?? "-"}</strong>
                <span>
                  {progress.status ?? "-"} / {progress.mode ?? "-"} / {progress.updated_at ?? "-"}
                </span>
              </div>
              <div className="audit-progress-grid">
                <span>赛季</span>
                <strong>{progress.season ?? audit.season}</strong>
                <span>轮次</span>
                <strong>{formatNullableNumber(progress.round)}</strong>
                <span>当前处理</span>
                <strong>{formatNullableNumber(progress.processed_matches)}</strong>
                <span>当前快照</span>
                <strong>{formatNullableNumber(progress.inserted_snapshots)}</strong>
                <span>当前失败</span>
                <strong>{formatNullableNumber(progress.failed_matches)}</strong>
                <span>当前请求</span>
                <strong>{formatNullableNumber(progress.requests_used)}</strong>
              </div>
            </div>
          ) : (
            <div className="empty-state">暂无 worker 进度快照</div>
          )}
        </Panel>
        <Panel title="总计">
          <div className="audit-progress-grid">
            <span>已处理比赛</span>
            <strong>{formatNullableNumber(progress?.total_processed_matches)}</strong>
            <span>写入快照</span>
            <strong>{formatNullableNumber(progress?.total_inserted_snapshots)}</strong>
            <span>失败比赛</span>
            <strong>{formatNullableNumber(progress?.total_failed_matches)}</strong>
            <span>请求次数</span>
            <strong>{formatNullableNumber(progress?.total_requests_used)}</strong>
            <span>日志目录</span>
            <strong>{audit.log_dir}</strong>
          </div>
        </Panel>
      </section>
      <Panel title="联赛回填审计">
        <table>
          <thead>
            <tr>
              <th>联赛</th>
              <th>OddsPapi ID</th>
              <th>完赛</th>
              <th>已匹配</th>
              <th>有快照</th>
              <th>覆盖率</th>
              <th>快照</th>
              <th>亚盘</th>
              <th>大小球</th>
              <th>状态</th>
              <th>主要失败原因</th>
            </tr>
          </thead>
          <tbody>
            {leagueRows.map((league) => (
              <tr key={`${league.league_name}-${league.source_league_id ?? "none"}`}>
                <td>{league.league_display_name ?? league.league_name}</td>
                <td>{league.source_league_id ?? "-"}</td>
                <td>{league.finished_matches.toLocaleString()}</td>
                <td>{league.matched_matches.toLocaleString()}</td>
                <td>{league.snapshot_matches.toLocaleString()}</td>
                <td>{league.snapshot_coverage_ratio}</td>
                <td>{league.snapshot_count.toLocaleString()}</td>
                <td>{league.asian_handicap_snapshot_count.toLocaleString()}</td>
                <td>{league.total_goals_snapshot_count.toLocaleString()}</td>
                <td>{league.status_summary}</td>
                <td>{league.top_error}</td>
              </tr>
            ))}
          </tbody>
        </table>
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

function formatNullableNumber(value: number | null | undefined) {
  return value == null ? "-" : value.toLocaleString();
}

function formatShortDateTime(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function ModelTrainingView({
  actionInFlight,
  data,
  errorText,
  messageText,
  onFullRefresh,
  onRunAction
}: {
  actionInFlight: string | null;
  data: DashboardData;
  errorText: string | null;
  messageText: string | null;
  onFullRefresh: () => void;
  onRunAction: (action: "baseline-dataset" | "baseline-dataset-qa" | "market-baseline") => void;
}) {
  const workspace = data.trainingWorkspace;
  const latestRun = workspace.latest_run;
  const workflowCards = buildTrainingWorkspaceCards(workspace);
  const runCards = buildTrainingRunCards(latestRun);
  const marketRows = listTrainingMarketRows(workspace);
  const qualityIssues = countTrainingQualityIssues(workspace);
  const lowSampleLeagueText = formatLowSampleLeagues(workspace.qa.low_sample_leagues);
  const isFullRefreshRunning =
    actionInFlight === "full-refresh" || latestRun?.status === "running";

  return (
    <section className="single-column">
      <Panel title="训练编排">
        {messageText && <div className="inline-success">{messageText}</div>}
        {errorText && <div className="inline-warning">{errorText}</div>}
        {latestRun?.status === "failed" && latestRun.error_message && (
          <div className="inline-warning">
            {`失败步骤：${formatTrainingRunStep(latestRun.error_step)} / ${latestRun.error_message}`}
          </div>
        )}
        <div className="training-actions">
          <button disabled={isFullRefreshRunning} onClick={onFullRefresh} type="button">
            <Play size={16} />
            更新训练与模型报告
          </button>
          {latestRun && (
            <span>
              {formatTrainingRunStatus(latestRun.status)} /{" "}
              {formatTrainingRunStep(latestRun.current_step)}
            </span>
          )}
        </div>
        <section className="metrics compact-metrics">
          {runCards.map((card) => (
            <MetricCard key={card.label} label={card.label} value={card.value} />
          ))}
        </section>
        {latestRun && (
          <div className="training-status-grid orchestration-grid">
            <StatusLine
              label={`运行 ${latestRun.snapshot_tag} / ${formatTrainingRunStatus(latestRun.status)}`}
              path={`当前步骤：${formatTrainingRunStep(latestRun.current_step)}`}
              ready={latestRun.status !== "failed"}
            />
            {Object.entries(latestRun.artifact_paths)
              .filter(([, path]) => Boolean(path))
              .map(([key, path]) => (
                <StatusLine
                  key={key}
                  label={formatArtifactPathLabel(key)}
                  path={path ?? ""}
                  ready={latestRun.status === "success"}
                />
              ))}
          </div>
        )}
      </Panel>

      <section className="metrics compact-metrics">
        {workflowCards.map((card) => (
          <MetricCard key={card.label} label={card.label} value={card.value} />
        ))}
      </section>

      <section className="grid">
        <Panel title="训练工作流">
          {messageText && <div className="inline-success">{messageText}</div>}
          {errorText && <div className="inline-warning">{errorText}</div>}
          <div className="training-actions">
            <button
              disabled={actionInFlight !== null}
              onClick={() => onRunAction("baseline-dataset")}
              type="button"
            >
              <Play size={16} />
              生成训练集
            </button>
            <button
              disabled={actionInFlight !== null || !workspace.dataset.exists}
              onClick={() => onRunAction("baseline-dataset-qa")}
              type="button"
            >
              <FileCheck2 size={16} />
              执行 QA
            </button>
            <button
              disabled={actionInFlight !== null || !workspace.dataset.exists}
              onClick={() => onRunAction("market-baseline")}
              type="button"
            >
              <FlaskConical size={16} />
              跑市场基准
            </button>
            {actionInFlight && <span>正在执行 {formatTrainingAction(actionInFlight)}</span>}
          </div>
          <div className="training-status-grid">
            <StatusLine
              label={`训练集 ${workspace.dataset.row_count.toLocaleString()} 行 / ${
                workspace.dataset.column_count
              } 列`}
              path={workspace.dataset.path}
              ready={workspace.dataset.exists}
            />
            <StatusLine
              label="训练集报告"
              path={workspace.dataset_report.path}
              ready={workspace.dataset_report.exists}
            />
            <StatusLine label="QA 报告" path={workspace.qa.path} ready={workspace.qa.exists} />
            <StatusLine
              label="市场基准报告"
              path={workspace.market_baseline.path}
              ready={workspace.market_baseline.exists}
            />
          </div>
        </Panel>

        <Panel title="数据质量">
          <div className="training-quality-list">
            <div>
              <span>必填空值</span>
              <strong className={workspace.qa.empty_required_cells > 0 ? "negative-number" : ""}>
                {workspace.qa.empty_required_cells.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>赔率异常</span>
              <strong className={workspace.qa.invalid_odds_cells > 0 ? "negative-number" : ""}>
                {workspace.qa.invalid_odds_cells.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>概率异常</span>
              <strong
                className={workspace.qa.invalid_probability_cells > 0 ? "negative-number" : ""}
              >
                {workspace.qa.invalid_probability_cells.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>Overround 异常</span>
              <strong
                className={workspace.qa.invalid_overround_cells > 0 ? "negative-number" : ""}
              >
                {workspace.qa.invalid_overround_cells.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>Thin history</span>
              <strong>{`${workspace.qa.thin_history_count.toLocaleString()} / ${
                workspace.qa.thin_history_ratio
              }`}</strong>
            </div>
            <div>
              <span>低样本联赛</span>
              <strong>{lowSampleLeagueText}</strong>
            </div>
          </div>
          <p className={qualityIssues > 0 ? "training-note warning" : "training-note"}>
            {qualityIssues > 0
              ? "当前训练集仍有质量问题，建议先修复再进入模型特征阶段。"
              : "当前 baseline 训练集没有发现必填、赔率、概率或 overround 结构性问题。"}
          </p>
        </Panel>
      </section>

      <Panel title="Close-market 基准">
        <table>
          <thead>
            <tr>
              <th>盘口</th>
              <th>评估样本</th>
              <th>跳过</th>
              <th>Accuracy</th>
              <th>Log Loss</th>
              <th>Brier</th>
              <th>Flat ROI</th>
            </tr>
          </thead>
          <tbody>
            {marketRows.map((row) => (
              <tr key={row.marketType}>
                <td>{row.marketLabel}</td>
                <td>{row.evaluatedCount.toLocaleString()}</td>
                <td>{row.skippedCount.toLocaleString()}</td>
                <td>{row.accuracy}</td>
                <td>{row.logLoss}</td>
                <td>{row.brier}</td>
                <td className={row.flatBetRoi.startsWith("-") ? "negative-number" : "positive-number"}>
                  {row.flatBetRoi}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

    </section>
  );
}

function StatusLine({ label, path, ready }: { label: string; path: string; ready: boolean }) {
  return (
    <div className="status-line">
      <span className={`status-pill ${ready ? "ready" : "failed"}`}>{ready ? "可用" : "缺失"}</span>
      <div>
        <strong>{label}</strong>
        <code>{path}</code>
      </div>
    </div>
  );
}

function formatLowSampleLeagues(leagues: Record<string, number>) {
  const entries = Object.entries(leagues);
  if (entries.length === 0) {
    return "-";
  }
  return entries.map(([league, count]) => `${league} ${count}`).join(" / ");
}

function formatTrainingAction(action: string) {
  const names: Record<string, string> = {
    "baseline-dataset": "生成训练集",
    "baseline-dataset-qa": "执行 QA",
    "market-baseline": "市场基准"
  };
  return names[action] ?? action;
}

function formatArtifactPathLabel(key: string) {
  const names: Record<string, string> = {
    away_cover_stability_report_path: "客队方向稳定性报告",
    dataset_path: "训练集 CSV",
    dataset_report_path: "训练集报告",
    dynamic_feature_path: "动态特征 CSV",
    dynamic_feature_report_path: "动态特征报告",
    feature_path: "基础特征 CSV",
    feature_report_path: "基础特征报告",
    market_baseline_report_path: "市场基准报告",
    qa_report_path: "QA 报告"
  };
  return names[key] ?? key;
}

function PaperTrackingView({
  actionInFlight,
  data,
  errorText,
  filters,
  messageText,
  onBatchRecord,
  onEdit,
  onFiltersChange,
  onRecord,
  onRefresh,
  onSettle,
  onVoid
}: {
  actionInFlight: string | null;
  data: DashboardData;
  errorText: string | null;
  filters: PaperFilterState;
  messageText: string | null;
  onBatchRecord: (candidates: PaperCandidate[]) => void;
  onEdit: (
    record: PaperRecord,
    payload: { current_market_line: string; current_odds: string; manual_note: string }
  ) => void;
  onFiltersChange: (filters: Partial<PaperFilterState>) => void;
  onRecord: (candidate: PaperCandidate) => void;
  onRefresh: () => void;
  onSettle: () => void;
  onVoid: (record: PaperRecord) => void;
}) {
  const workspace = data.paperRecommendations;
  const cards = buildPaperSummaryCards(workspace);
  const groups = buildPaperRecordGroups(workspace);
  const recordableCandidates = workspace.candidates.filter(
    (candidate) => candidate.is_recordable && candidate.status === "candidate"
  );
  const isBusy = actionInFlight !== null;

  return (
    <section className="single-column">
      <section className="metrics">
        {cards.map((card) => (
          <MetricCard key={card.label} label={card.label} value={card.value} />
        ))}
      </section>
      <Panel title="操作">
        <div className="action-row">
          <label>
            <span>开始</span>
            <input
              onChange={(event) => onFiltersChange({ start_time: event.target.value })}
              type="datetime-local"
              value={filters.start_time}
            />
          </label>
          <label>
            <span>结束</span>
            <input
              onChange={(event) => onFiltersChange({ end_time: event.target.value })}
              type="datetime-local"
              value={filters.end_time}
            />
          </label>
          <button disabled={isBusy} onClick={onRefresh} type="button">
            刷新候选
          </button>
          <button
            disabled={isBusy || recordableCandidates.length === 0}
            onClick={() => onBatchRecord(recordableCandidates)}
            type="button"
          >
            批量记录候选
          </button>
          <button disabled={isBusy} onClick={onSettle} type="button">
            结算已完赛
          </button>
          {actionInFlight && <span>正在执行 {formatPaperAction(actionInFlight)}</span>}
          {messageText && <span className="success-text">{messageText}</span>}
          {errorText && <span className="error-text">{errorText}</span>}
        </div>
      </Panel>
      <Panel title="候选队列">
        <PaperCandidateTable
          isBusy={isBusy}
          onRecordAll={onBatchRecord}
          onRecord={onRecord}
          workspace={workspace}
        />
      </Panel>
      <Panel title="纸面记录">
        <PaperRecordTable
          isBusy={isBusy}
          onEdit={onEdit}
          onVoid={onVoid}
          records={workspace.records}
        />
      </Panel>
      <section className="grid">
        <Panel title="按策略">
          <PaperGroupTable groups={groups.byStrategy} />
        </Panel>
        <Panel title="按联赛">
          <PaperGroupTable groups={groups.byLeague} />
        </Panel>
      </section>
      <section className="grid">
        <Panel title="按盘口桶">
          <PaperGroupTable groups={groups.byLineBucket} />
        </Panel>
        <Panel title="按人工调整">
          <PaperGroupTable groups={groups.byManualAdjustment} />
        </Panel>
      </section>
    </section>
  );
}

function PaperGroupTable({
  groups
}: {
  groups: ReturnType<typeof buildPaperRecordGroups>["byStrategy"];
}) {
  if (groups.length === 0) {
    return <div className="empty-state">暂无已结算记录</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>分组</th>
          <th>记录</th>
          <th>已结算</th>
          <th>命中率</th>
          <th>盈亏</th>
          <th>ROI</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((group) => (
          <tr key={group.groupName}>
            <td>{group.groupName}</td>
            <td>{group.recordCount}</td>
            <td>{group.settledRecords}</td>
            <td>{group.hitRate}</td>
            <td>{group.profitUnits}</td>
            <td>{group.roi}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function refreshPaperWorkspace(
  setData: React.Dispatch<React.SetStateAction<DashboardData>>,
  filters: PaperFilterState = { end_time: "", start_time: "" }
): Promise<void> {
  return loadPaperRecommendationWorkspace(filters).then((workspace) => {
    setData((current) => ({ ...current, paperRecommendations: workspace }));
  });
}

function formatPaperAction(action: string) {
  if (action === "refresh") {
    return "刷新候选";
  }
  if (action === "batch-record") {
    return "批量记录";
  }
  if (action === "settle") {
    return "结算";
  }
  if (action.startsWith("record-")) {
    return "记录观察";
  }
  if (action.startsWith("edit-")) {
    return "编辑记录";
  }
  if (action.startsWith("void-")) {
    return "作废记录";
  }
  return action;
}

function RecordsView({ data }: { data: DashboardData }) {
  const summary = buildRecommendationRecordSummary(data.recommendationRecords);
  const groups = buildRecommendationRecordGroups(data.recommendationRecords);

  return (
    <section className="single-column">
      <section className="metrics">
        <MetricCard label="推荐数" value={summary.totalRecords.toLocaleString()} />
        <MetricCard label="已复盘" value={summary.settledRecords.toLocaleString()} />
        <MetricCard label="总手数" value={summary.totalStakeUnits} />
        <MetricCard label="盈亏" value={summary.totalProfitUnits} tone="warning" />
        <MetricCard label="ROI" value={summary.roi} />
      </section>
      <section className="grid">
        <Panel title="按盘口类型">
          <RecordGroupTable groups={groups.byMarketType} />
        </Panel>
        <Panel title="按信心等级">
          <RecordGroupTable groups={groups.byConfidenceGrade} />
        </Panel>
      </section>
      <Panel title="按联赛">
        <RecordGroupTable groups={groups.byLeague} />
      </Panel>
      <Panel title="推荐记录">
        <RecommendationRecordTable records={data.recommendationRecords} />
      </Panel>
    </section>
  );
}

function RecordGroupTable({
  groups
}: {
  groups: ReturnType<typeof buildRecommendationRecordGroups>["byMarketType"];
}) {
  if (groups.length === 0) {
    return <div className="empty-state">暂无已复盘记录</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>分组</th>
          <th>记录</th>
          <th>命中率</th>
          <th>手数</th>
          <th>盈亏</th>
          <th>ROI</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((group) => (
          <tr key={group.groupName}>
            <td>{group.groupName}</td>
            <td>{group.recordCount}</td>
            <td>{group.hitRate}</td>
            <td>{group.stakeUnits}</td>
            <td>{group.profitUnits}</td>
            <td>{group.roi}</td>
          </tr>
        ))}
      </tbody>
    </table>
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
