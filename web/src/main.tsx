import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, BarChart3, CircleAlert, Database, ListChecks, Radio } from "lucide-react";
import "./styles.css";

type DashboardSummary = {
  total_matches: number;
  finished_matches: number;
  matches_with_historical_odds: number;
  historical_odds_snapshots: number;
  unmatched_matches: number;
};

type LeagueCoverage = {
  league_id: number;
  league_name: string;
  country_or_region: string;
  season: number;
  finished_matches: number;
  matches_with_historical_odds: number;
  coverage_ratio: string;
  unmatched_matches: number;
};

type WorkerStatus = {
  pid: number;
  status: string;
  mode: string;
  season: number;
  league_ids: string[];
  process_log_path: string;
  notify_on_complete: boolean;
};

type UnmatchedMatch = {
  match_id: number;
  league_name: string;
  home_team_name: string;
  away_team_name: string;
  kickoff_time: string;
  match_reason: string;
};

type OddsPoint = {
  snapshot_time: string;
  bookmaker: string;
  market_line: string;
  home_odds?: string;
  away_odds?: string;
  over_odds?: string;
  under_odds?: string;
};

const summary: DashboardSummary = {
  total_matches: 13112,
  finished_matches: 12980,
  matches_with_historical_odds: 1844,
  historical_odds_snapshots: 183204,
  unmatched_matches: 217
};

const leagues: LeagueCoverage[] = [
  {
    league_id: 40,
    league_name: "英冠",
    country_or_region: "England",
    season: 2025,
    finished_matches: 552,
    matches_with_historical_odds: 494,
    coverage_ratio: "0.8949",
    unmatched_matches: 12
  },
  {
    league_id: 78,
    league_name: "德甲",
    country_or_region: "Germany",
    season: 2025,
    finished_matches: 306,
    matches_with_historical_odds: 286,
    coverage_ratio: "0.9346",
    unmatched_matches: 4
  },
  {
    league_id: 283,
    league_name: "罗甲",
    country_or_region: "Romania",
    season: 2025,
    finished_matches: 240,
    matches_with_historical_odds: 18,
    coverage_ratio: "0.0750",
    unmatched_matches: 33
  }
];

const workers: WorkerStatus[] = [
  {
    pid: 27776,
    status: "running",
    mode: "balanced",
    season: 2025,
    league_ids: ["106", "114", "119", "128", "203", "235", "265", "283"],
    process_log_path: "logs/odds/20260525-210422-oddspapi-worker-process.log",
    notify_on_complete: true
  }
];

const unmatched: UnmatchedMatch[] = [
  {
    match_id: 1002,
    league_name: "英超",
    home_team_name: "Wolves",
    away_team_name: "Leeds",
    kickoff_time: "2026-05-21T22:00:00+08:00",
    match_reason: "未匹配到 OddsPapi 比赛"
  },
  {
    match_id: 1308,
    league_name: "土超",
    home_team_name: "Istanbul Basaksehir",
    away_team_name: "Rizespor",
    kickoff_time: "2026-05-18T01:00:00+08:00",
    match_reason: "队名相似度低于阈值"
  }
];

const asianHandicap: OddsPoint[] = [
  { snapshot_time: "12:00", bookmaker: "pinnacle", market_line: "-0.25", home_odds: "1.93", away_odds: "1.95" },
  { snapshot_time: "16:00", bookmaker: "pinnacle", market_line: "-0.25", home_odds: "1.89", away_odds: "1.99" },
  { snapshot_time: "20:00", bookmaker: "pinnacle", market_line: "-0.50", home_odds: "2.04", away_odds: "1.84" }
];

const totalGoals: OddsPoint[] = [
  { snapshot_time: "12:00", bookmaker: "pinnacle", market_line: "2.50", over_odds: "1.91", under_odds: "1.97" },
  { snapshot_time: "16:00", bookmaker: "pinnacle", market_line: "2.50", over_odds: "1.86", under_odds: "2.02" },
  { snapshot_time: "20:00", bookmaker: "pinnacle", market_line: "2.75", over_odds: "2.01", under_odds: "1.87" }
];

function App() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">冰酒预测</div>
        <nav>
          <a className="active"><Activity size={18} />总览</a>
          <a><Database size={18} />覆盖率</a>
          <a><Radio size={18} />Worker</a>
          <a><CircleAlert size={18} />未匹配</a>
          <a><BarChart3 size={18} />赔率走势</a>
          <a><ListChecks size={18} />推荐记录</a>
        </nav>
      </aside>
      <main className="content">
        <section className="topbar">
          <div>
            <h1>控制台总览</h1>
            <p>本地数据回填、赔率覆盖和模型推荐的工作台</p>
          </div>
          <span className="status-dot">后台回填运行中</span>
        </section>

        <section className="metrics">
          <Metric label="比赛总数" value={summary.total_matches.toLocaleString()} />
          <Metric label="完赛场次" value={summary.finished_matches.toLocaleString()} />
          <Metric label="有赔率场次" value={summary.matches_with_historical_odds.toLocaleString()} />
          <Metric label="赔率快照" value={summary.historical_odds_snapshots.toLocaleString()} />
          <Metric label="未匹配" value={summary.unmatched_matches.toLocaleString()} tone="warning" />
        </section>

        <section className="grid">
          <Panel title="联赛覆盖率">
            <table>
              <thead>
                <tr>
                  <th>联赛</th>
                  <th>赛季</th>
                  <th>完赛</th>
                  <th>有赔率</th>
                  <th>覆盖率</th>
                  <th>未匹配</th>
                </tr>
              </thead>
              <tbody>
                {leagues.map((league) => (
                  <tr key={league.league_id}>
                    <td>{league.league_name}</td>
                    <td>{league.season}</td>
                    <td>{league.finished_matches}</td>
                    <td>{league.matches_with_historical_odds}</td>
                    <td>{(Number(league.coverage_ratio) * 100).toFixed(1)}%</td>
                    <td>{league.unmatched_matches}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="Worker 状态">
            {workers.map((worker) => (
              <div className="worker" key={worker.pid}>
                <div>
                  <strong>pid={worker.pid}</strong>
                  <span>{worker.mode} / {worker.season}</span>
                </div>
                <p>{worker.league_ids.join(", ")}</p>
                <code>{worker.process_log_path}</code>
              </div>
            ))}
          </Panel>
        </section>

        <section className="grid">
          <Panel title="单场赔率走势">
            <Trend title="亚盘" points={asianHandicap} firstKey="home_odds" secondKey="away_odds" />
            <Trend title="大小球" points={totalGoals} firstKey="over_odds" secondKey="under_odds" />
          </Panel>

          <Panel title="待处理未匹配">
            <div className="unmatched-list">
              {unmatched.map((item) => (
                <div className="unmatched" key={item.match_id}>
                  <strong>{item.league_name}</strong>
                  <span>{item.home_team_name} vs {item.away_team_name}</span>
                  <small>{item.match_reason}</small>
                </div>
              ))}
            </div>
          </Panel>
        </section>
      </main>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warning" }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Trend({
  title,
  points,
  firstKey,
  secondKey
}: {
  title: string;
  points: OddsPoint[];
  firstKey: keyof OddsPoint;
  secondKey: keyof OddsPoint;
}) {
  return (
    <div className="trend">
      <div className="trend-title">{title}</div>
      <div className="trend-bars">
        {points.map((point) => (
          <div className="trend-point" key={`${title}-${point.snapshot_time}`}>
            <span>{point.snapshot_time}</span>
            <div className="bar-stack">
              <i style={{ height: `${Number(point[firstKey] ?? 1.8) * 38}px` }} />
              <b style={{ height: `${Number(point[secondKey] ?? 1.8) * 38}px` }} />
            </div>
            <em>{point.market_line}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
