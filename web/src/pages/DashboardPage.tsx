import { useEffect, useState } from "react";
import { Activity, BarChart3, CircleAlert, Database, ListChecks, Radio } from "lucide-react";

import { loadDashboardData } from "../apiClient";
import { LeagueCoverageTable } from "../components/LeagueCoverageTable";
import { MetricCard } from "../components/MetricCard";
import { OddsTrendPanel } from "../components/OddsTrendPanel";
import { Panel } from "../components/Panel";
import { UnmatchedTable } from "../components/UnmatchedTable";
import { WorkerStatusTable } from "../components/WorkerStatusTable";
import { mockDashboardData } from "../mockData";
import type { DashboardData } from "../types";

export function DashboardPage() {
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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">冰酒预测</div>
        <nav>
          <a className="active">
            <Activity size={18} />
            总览
          </a>
          <a>
            <Database size={18} />
            覆盖率
          </a>
          <a>
            <Radio size={18} />
            Worker
          </a>
          <a>
            <CircleAlert size={18} />
            未匹配
          </a>
          <a>
            <BarChart3 size={18} />
            赔率走势
          </a>
          <a>
            <ListChecks size={18} />
            推荐记录
          </a>
        </nav>
      </aside>
      <main className="content">
        <section className="topbar">
          <div>
            <h1>控制台总览</h1>
            <p>本地数据回填、赔率覆盖和模型推荐的工作台</p>
          </div>
          <span className="status-dot">
            {isLoading ? "正在加载" : data.source === "api" ? "真实接口" : "Mock 数据"}
          </span>
        </section>

        <section className="metrics">
          <MetricCard label="比赛总数" value={data.summary.total_matches.toLocaleString()} />
          <MetricCard label="完赛场次" value={data.summary.finished_matches.toLocaleString()} />
          <MetricCard
            label="有赔率场次"
            value={data.summary.matches_with_historical_odds.toLocaleString()}
          />
          <MetricCard
            label="赔率快照"
            value={data.summary.historical_odds_snapshots.toLocaleString()}
          />
          <MetricCard
            label="未匹配"
            value={data.summary.unmatched_matches.toLocaleString()}
            tone="warning"
          />
        </section>

        <section className="grid">
          <Panel title="联赛覆盖率">
            <LeagueCoverageTable leagues={data.leagues} />
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
            <UnmatchedTable matches={data.unmatched} />
          </Panel>
        </section>
      </main>
    </div>
  );
}
