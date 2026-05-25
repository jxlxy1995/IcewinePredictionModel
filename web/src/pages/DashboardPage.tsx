import { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, CircleAlert, Database, ListChecks, Radio } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { loadDashboardData } from "../apiClient";
import { LeagueCoverageTable } from "../components/LeagueCoverageTable";
import { MetricCard } from "../components/MetricCard";
import { OddsTrendPanel } from "../components/OddsTrendPanel";
import { Panel } from "../components/Panel";
import { UnmatchedTable } from "../components/UnmatchedTable";
import { WorkerStatusTable } from "../components/WorkerStatusTable";
import { mockDashboardData } from "../mockData";
import type { DashboardData } from "../types";

type ViewKey = "overview" | "coverage" | "workers" | "unmatched" | "odds" | "records";

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

  useEffect(() => {
    let isMounted = true;
    loadDashboardData().then((loadedData) => {
      if (!isMounted) {
        return;
      }
      setData(loadedData);
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

        {activeView === "overview" && <OverviewView data={data} />}
        {activeView === "coverage" && <CoverageView data={data} />}
        {activeView === "workers" && <WorkersView data={data} />}
        {activeView === "unmatched" && <UnmatchedView data={data} />}
        {activeView === "odds" && <OddsView data={data} />}
        {activeView === "records" && <RecordsView />}
      </main>
    </div>
  );
}

function OverviewView({ data }: { data: DashboardData }) {
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
          <OddsTrendPanel trends={data.oddsTrends} />
        </Panel>
        <Panel title="待处理未匹配">
          <UnmatchedTable matches={data.unmatched.slice(0, 6)} />
        </Panel>
      </section>
    </>
  );
}

function CoverageView({ data }: { data: DashboardData }) {
  return (
    <>
      <SummaryMetrics data={data} />
      <Panel title="全部联赛覆盖率">
        <LeagueCoverageTable leagues={data.leagues} />
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

function OddsView({ data }: { data: DashboardData }) {
  return (
    <section className="single-column">
      <Panel title="赔率走势预览">
        <OddsTrendPanel trends={data.oddsTrends} />
      </Panel>
    </section>
  );
}

function RecordsView() {
  return (
    <section className="single-column">
      <Panel title="推荐记录">
        <div className="record-placeholder">
          <div>
            <strong>下一阶段接入</strong>
            <span>推荐记录、信心等级、出手手数和复盘收益</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>比赛</th>
                <th>盘口</th>
                <th>信心</th>
                <th>手数</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Cardiff vs Swansea</td>
                <td>亚盘 -0.25 主队</td>
                <td>A-</td>
                <td>1.50</td>
                <td>待复盘</td>
              </tr>
              <tr>
                <td>Roma vs Lazio</td>
                <td>大小球 2.75 大</td>
                <td>B+</td>
                <td>1.00</td>
                <td>待复盘</td>
              </tr>
            </tbody>
          </table>
        </div>
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
