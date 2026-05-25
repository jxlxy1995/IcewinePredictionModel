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
  loadTeamDisplayNameWorkspace
} from "../apiClient";
import { LeagueCoverageTable } from "../components/LeagueCoverageTable";
import { MetricCard } from "../components/MetricCard";
import { OddsTrendPanel } from "../components/OddsTrendPanel";
import { Panel } from "../components/Panel";
import { RecommendationRecordTable } from "../components/RecommendationRecordTable";
import { TeamDisplayNameEditor } from "../components/TeamDisplayNameEditor";
import { UnmatchedTable } from "../components/UnmatchedTable";
import { WorkerStatusTable } from "../components/WorkerStatusTable";
import { mockDashboardData } from "../mockData";
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
  const [teamDisplayWorkspace, setTeamDisplayWorkspace] = useState<TeamDisplayNameWorkspace | null>(
    null
  );
  const [displayWorkspaceError, setDisplayWorkspaceError] = useState<string | null>(null);
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
      setOddsTrends(loadedData.oddsTrends);
      setSelectedOddsMatchId(loadedData.oddsTrends.match_id);
      const firstMissingTeam = loadedData.missingTeamDisplayNames[0];
      if (firstMissingTeam?.season != null) {
        loadTeamDisplayNameWorkspace(firstMissingTeam.league_id, firstMissingTeam.season)
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
            filterText={displayNameFilter}
            onFilterTextChange={setDisplayNameFilter}
            onWorkspaceChange={(leagueId, season) => {
              setDisplayWorkspaceError(null);
              loadTeamDisplayNameWorkspace(leagueId, season)
                .then(setTeamDisplayWorkspace)
                .catch(() => setDisplayWorkspaceError("读取球队中文名维护列表失败"));
            }}
            workspace={teamDisplayWorkspace}
            workspaceError={displayWorkspaceError}
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
  filterText,
  onFilterTextChange,
  onWorkspaceChange,
  workspace,
  workspaceError
}: {
  data: DashboardData;
  filterText: string;
  onFilterTextChange: (value: string) => void;
  onWorkspaceChange: (leagueId: number, season: number) => void;
  workspace: TeamDisplayNameWorkspace | null;
  workspaceError: string | null;
}) {
  const workspaceOptions = Array.from(
    new Map(
      data.missingTeamDisplayNames
        .filter((item) => item.season != null)
        .map((item) => [
          `${item.league_id}-${item.season}`,
          {
            league_id: item.league_id,
            league_name: item.league_name,
            league_display_name: item.league_display_name,
            season: item.season as number
          }
        ])
    ).values()
  );
  const normalizedFilterText = filterText.trim().toLowerCase();
  const visibleTeams = (workspace?.teams ?? []).filter((item) => {
    if (!normalizedFilterText) {
      return true;
    }
    return `${item.league_display_name ?? ""} ${item.league_name} ${item.season ?? ""} ${item.team_name}`
      .toLowerCase()
      .includes(normalizedFilterText);
  });

  return (
    <section className="single-column">
      <Panel title="缺失中文名球队">
        <div className="table-toolbar">
          <select
            onChange={(event) => {
              const [leagueId, season] = event.target.value.split("-").map(Number);
              onWorkspaceChange(leagueId, season);
            }}
            value={workspace ? `${workspace.league_id}-${workspace.season}` : ""}
          >
            {workspaceOptions.map((option) => (
              <option key={`${option.league_id}-${option.season}`} value={`${option.league_id}-${option.season}`}>
                {option.league_display_name ?? option.league_name} · {option.season}
              </option>
            ))}
          </select>
          <input
            onChange={(event) => onFilterTextChange(event.target.value)}
            placeholder="筛选联赛、赛季或球队英文名"
            type="search"
            value={filterText}
          />
        </div>
        {workspaceError && <div className="inline-warning">{workspaceError}</div>}
        {workspace && (
          <div className="match-heading">
            <strong>
              {workspace.league_display_name ?? workspace.league_name} · {workspace.season}
            </strong>
            <span>{workspace.teams.length} 支球队</span>
          </div>
        )}
        <TeamDisplayNameEditor teams={visibleTeams} />
      </Panel>
    </section>
  );
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
