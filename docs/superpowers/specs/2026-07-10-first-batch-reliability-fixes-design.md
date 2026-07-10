# 第一批可靠性修复设计

## 目标

在不改变推荐策略、模型输出和数据库结构的前提下，修复自动任务阻塞、前端写操作假成功和推荐队列潜在类型错误，并补充校准 edge 的语义注释。

## 自动任务恢复与领取

- 调度器继续保持同一时间只运行一个自动任务。
- `running` 任务在 `started_at` 距当前时间超过运行超时后视为遗留任务，标记为 `failed`，记录明确错误信息和完成时间，再允许后续任务被领取。
- 默认运行超时为 360 分钟，通过 `PAPER_AUTOMATION_RUNNING_TIMEOUT_MINUTES` 配置；非法或非正数配置回退到默认值。
- 未超时的 `running` 任务仍阻止领取新任务。
- 待执行任务使用同时包含 `status == "pending"` 和 `NOT EXISTS(status == "running")` 的更新完成领取；只有实际更新一行的调度器获得任务，既避免同一任务重复领取，也避免不同任务并发运行。
- 任务的成功、失败和超时回收都只在当前状态仍为 `running` 时更新，避免旧执行器覆盖其他调度器已经写入的终态。
- 不增加数据库字段或迁移。

## 前端错误传播

- `markTeamDisplayNameWorkspaceDone` 和 `saveTeamDisplayNames` 不再捕获写请求失败并返回内存 mock 成功结果。
- HTTP 错误和网络错误沿现有 Promise 链传播，由页面现有错误提示处理。
- 只读接口当前的 mock 回退行为不在本批范围内。

## 推荐队列潜在错误

- 删除未被调用且参数类型已经失效的 `_latest_historical_snapshots_for_match`，同时删除仅由它调用的 `_select_latest_pre_kickoff_pair`。
- 保留并验证当前生产路径 `_historical_snapshots_for_execution_target` 的行为。
- 不改变标准时点、赔率来源优先级或鲁棒性规则。

## 校准 edge 注释

- 在 `calibrated_edge` 赋值附近增加简短注释：该值是校准模型对原始模型所选方向的 edge。
- 不修改字段名、计算下标、共识判断或外部输出。

## 验证

- 后端聚焦测试：自动任务服务、调度器、Web API 和纸面推荐队列。
- 前端聚焦测试：`apiClient.test.ts`。
- 完整验证：787 项 Python 测试、88 项前端测试、TypeScript/Vite 生产构建。
