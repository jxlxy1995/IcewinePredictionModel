import type { WorkerStatus } from "../types";

type WorkerStatusTableProps = {
  workers: WorkerStatus[];
};

export function WorkerStatusTable({ workers }: WorkerStatusTableProps) {
  if (workers.length === 0) {
    return <div className="empty-state">暂无后台 Worker 状态</div>;
  }
  return (
    <div className="worker-list">
      {workers.map((worker) => (
        <div className="worker" key={worker.pid}>
          <div>
            <strong>pid={worker.pid}</strong>
            <span>
              {worker.mode ?? "-"} / {worker.season ?? "-"}
            </span>
          </div>
          <p>{worker.league_ids.join(", ") || "未指定联赛"}</p>
          <code>{worker.process_log_path ?? "暂无日志路径"}</code>
        </div>
      ))}
    </div>
  );
}
