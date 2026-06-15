# 纸面自动任务队列设计

## 背景

这个功能服务于一种很具体的使用场景：用户已经确认某个时间点有比赛，但届时无法手动操作 Web 控制台。

典型流程是：

1. 先在比赛列表页确认某个开赛时间段有目标比赛。
2. 离开电脑前创建一个一次性自动任务。
3. 到触发时间后，系统自动执行赔率回填、刷新纸面候选、批量记录可记录候选，并通过 Bark 推送结果到手机。

第一版要保持克制：不改变比赛列表现有行为，不增加比赛预览或勾选比赛 UI。

## 目标

- 增加一个由 Web 管理的一次性纸面自动任务队列。
- 在比赛列表页提供一个轻量创建入口，业务输入只包含：
  - 任务触发时间
  - 目标比赛开赛时间段
- 增加独立的“自动任务”页面，用于查看任务状态、详情、取消任务和 Bark 推送诊断。
- Web 后端运行期间自动执行到点任务。
- 第一版全局串行执行任务，降低 OddsPapi / API-Football 请求、限流和状态混乱风险。
- 支持以下情况的 Bark 推送：
  - 成功并记录了推荐
  - 成功但没有候选
  - 部分比赛赔率回填失败但任务继续完成
  - 任务失败
  - Bark 推送自身失败，前提是仍能记录到控制台
- 所有成功进入最终纸面推荐组的推荐，都必须出现在 Bark 推送里。不能因为消息过长而截断推荐明细。
- Bark 推荐明细必须使用和 Web 纸面推荐记录页完全一致的评分和建议手数。

## 非目标

- 第一版不做周期性 cron 任务模板。
- 第一版不支持按联赛、搜索词、状态或手动勾选比赛过滤。
- 自动任务创建弹窗里不做比赛预览。
- Web 页面不录入 Bark key 或完整 Bark URL。
- 不允许取消正在运行的任务。
- 第一版不拆出独立 automation worker 进程。

## 数据模型

新增表：`paper_automation_tasks`。

字段：

- `id`
- `created_at`
- `updated_at`
- `created_by`：第一版固定为 `web`
- `trigger_at`：任务触发时间
- `match_window_start`：目标比赛开赛时间段开始
- `match_window_end`：目标比赛开赛时间段结束
- `status`：任务主状态
- `notification_status`：Bark 推送状态
- `notification_error`：Bark 推送失败原因
- `started_at`
- `finished_at`
- `missed_at`
- `cancelled_at`
- `error_message`：任务主流程失败原因
- `result_payload`：JSON 文本，保存执行摘要和通知内容

第一版任务表不保存 Bark URL、不保存动作链配置、不保存联赛筛选、不保存搜索筛选，也不保存手动选择的比赛 ID。

### 任务状态

任务主状态：

- `pending`：待执行
- `running`：执行中
- `success`：主流程成功
- `failed`：主流程失败
- `missed`：错过触发时间且超过宽限期
- `cancelled`：已取消

状态流转：

```text
pending -> running -> success
pending -> running -> failed
pending -> missed
pending -> cancelled
```

Bark 推送状态：

- `not_configured`：未配置 Bark
- `pending`：待推送
- `sent`：已推送
- `failed`：推送失败
- `skipped`：无需推送或被跳过

Bark 推送结果不能改变任务主流程结果。如果纸面自动流程成功，但 Bark 推送失败，应保存为：

```text
status = success
notification_status = failed
notification_error = <失败原因>
```

这样控制台可以清楚区分“任务成功”和“手机没有收到推送”。

## 配置

使用本地 `.env` 或环境变量。密钥和完整 URL 不提交到 GitHub。

```env
BARK_PUSH_URL=https://api.day.app/xxxxxx
PAPER_AUTOMATION_GRACE_MINUTES=20
PAPER_AUTOMATION_POLL_SECONDS=20
```

默认值：

- `PAPER_AUTOMATION_GRACE_MINUTES`：`20`
- `PAPER_AUTOMATION_POLL_SECONDS`：`20`

轮询间隔可以宽松到 20-30 秒。第一版默认 20 秒。

## 时间处理

Web UI 输入和展示均使用北京时间语义。后端解析任务输入时，应和比赛列表、纸面推荐页面保持同样的北京时间口径。

数据库存储可以沿用项目现有 datetime 约定，但所有用户可见的自动任务时间都必须格式化为北京时间：

- 任务触发时间
- 目标比赛时间段
- 任务创建、更新、开始、完成、错过、取消时间
- Bark 推送中的时间
- 任务详情和错误时间

## 创建规则

`POST /api/paper-automation/tasks` 请求体：

```json
{
  "trigger_at": "2026-06-15T18:21",
  "match_window_start": "2026-06-15T18:30",
  "match_window_end": "2026-06-15T18:30"
}
```

校验规则：

- `trigger_at` 必须是未来时间。
- `match_window_end >= match_window_start`。
- 本地数据库必须已经存在至少一场 kickoff 落在目标时间段内的比赛。否则拒绝创建，并提示用户先在比赛列表拉取或确认赛程。
- 如果已经存在相同 `trigger_at`、`match_window_start`、`match_window_end` 的 `pending` 或 `running` 任务，应拒绝或明确提示重复。
- Bark 未配置不阻止任务创建，但创建响应要返回警告，任务执行后保存 `notification_status = not_configured`。

目标比赛只按 kickoff 时间段筛选，不继承比赛列表页当前的联赛、搜索、状态等筛选条件。

## 调度器

Web 后端启动时启动一个轻量轮询器。

每轮轮询逻辑：

1. 如果已有任务处于 `running`，本轮不启动新任务。
2. 按 `trigger_at` 升序查找最早的 `pending` 任务。
3. 如果 `now < trigger_at`，不执行。
4. 如果 `now > trigger_at + grace_minutes`，将任务标记为 `missed`。
5. 否则在数据库事务中将任务抢占为 `running`。
6. 执行固定工作流。
7. 保存 `success` 或 `failed`、`finished_at`、`result_payload`。
8. 发送 Bark，并单独保存通知状态。

`pending -> running` 的抢占必须在事务中完成，避免后端重启或轮询重叠时重复执行同一任务。

第一版任务全局串行。如果后续任务因为等待前一个 `running` 任务而超过自身宽限时间，应标记为 `missed`。

## 执行流程

每个任务固定执行：

1. 按 kickoff 时间窗选择目标比赛。
2. 对目标比赛执行赔率回填或赔率同步。
3. 使用同一个时间窗构建纸面推荐候选队列。
4. 对 `status == "candidate"` 的候选创建纸面推荐记录。
5. 基于更新后的纸面记录重新构建纸面跟踪和信心模拟工作区。
6. 使用 Web 纸面推荐记录页同一套推荐组结果格式化 Bark 推送。
7. 发送 Bark。
8. 将执行摘要和错误写入 `result_payload`。

### 部分赔率失败

如果目标时间段内有多场比赛，其中某一场赔率回填失败，任务应继续执行。

例子：

- 比赛 A 赔率回填成功
- 比赛 B 赔率回填失败
- 比赛 C 赔率回填成功

任务应继续进入候选生成。失败的比赛如果无法满足候选条件，会自然表现为 `no_odds`、`stale_odds` 或其他诊断状态。每场失败摘要要写入 `result_payload` 和 Bark。

只有系统性异常才应让任务变成 `failed`，例如数据库失败、整个同步调用未处理异常、候选生成异常、批量记录异常。

### 无候选

没有候选也是一次成功执行：

```text
status = success
created_records = 0
```

Bark 仍然必须发送完成回执，包含目标时间窗、赔率摘要、候选数量、记录数量和诊断计数。

## 纸面记录与信心模拟一致性

纸面记录仍写入现有 `paper_recommendation_records`。

创建记录后，必须使用现有 `build_paper_confidence_workspace(...)` 逻辑重新构建纸面信心模拟工作区。Bark 推荐明细必须来自这个信心模拟推荐组，不能临时用 `edge` 或 `scoring_edge` 另算一套评分。

这是硬性要求，目的是保证手机推送和 Web 纸面推荐记录页在以下内容上完全一致：

- 推荐分组
- 推荐文本
- 评分
- 建议手数

Bark 明细应包含本次任务新创建记录所影响的每一个推荐组。如果同一场、同一市场、同一方向有多个策略被记录，Bark 应像 Web 纸面推荐记录页一样只显示聚合后的推荐组。

## Bark 消息格式

使用适合手机阅读的简洁中文。

成功并记录推荐：

```text
纸面自动任务：已记录 3 条
窗口：18:30 - 18:30
回填：3场 成功3 失败0

1. 日职联 横滨水手 vs 神户胜利船
   18:30 客队 +0.50  评分80  推荐1.50手

2. 韩K 蔚山HD vs 首尔FC
   18:30 小 2.50  评分76  推荐1.00手
```

无候选：

```text
纸面自动任务：无候选
窗口：18:30 - 18:30
回填：3场 成功2 失败1
候选：0 记录：0

诊断：no_odds=1 robustness_filtered=2
```

任务失败：

```text
纸面自动任务：失败
窗口：18:30 - 18:30
阶段：刷新候选
错误：feature csv not found ...
```

不能因为消息过长而丢弃已记录推荐。如果需要，应拆成多条 Bark 推送：

```text
纸面自动任务：已记录 12 条（1/3）
纸面自动任务：已记录 12 条（2/3）
纸面自动任务：已记录 12 条（3/3）
```

每一条分片消息都应包含足够的时间窗和上下文信息，保证单独阅读也能理解。

## API

新增：

```text
GET    /api/paper-automation/tasks
POST   /api/paper-automation/tasks
GET    /api/paper-automation/tasks/{id}
POST   /api/paper-automation/tasks/{id}/cancel
```

列表响应应支持自动任务页展示：

- 任务 ID
- 触发时间
- 目标比赛时间段
- 主状态
- Bark 状态
- 目标比赛数量
- 创建的推荐组数量
- 更新时间
- 简短错误或摘要

详情响应应包含：

- 完整任务字段
- 赔率回填摘要
- 候选诊断
- 批量记录结果
- Bark 中包含的信心模拟推荐组
- Bark 标题、正文或分片消息
- Bark 错误
- 任务主流程错误

取消规则：

- 只允许取消 `pending` 任务。
- `running`、`success`、`failed`、`cancelled` 均拒绝取消。

## UI

### 比赛列表页

在比赛列表现有操作区附近增加一个轻量 `创建自动任务` 入口。

弹窗字段：

- `触发任务时间`
- `筛选比赛开始时间`
- `筛选比赛结束时间`

不要在比赛表格中新增任务列，不做比赛预览，不做勾选比赛。

创建成功后提示：

```text
自动任务已创建，将于 18:21 执行
```

如果目标时间段没有本地赛程，提示：

```text
该比赛时间段当前没有本地赛程，请先在比赛列表拉取/确认赛程后再创建自动任务
```

### 自动任务页

新增导航项：`自动任务`。

页面为紧凑的工作台式表格。

顶部指标：

- 待执行
- 执行中
- 今日完成
- 失败 / Bark 失败

主表：

- 触发时间
- 比赛时间段
- 任务状态
- 目标比赛数
- 创建推荐组数
- Bark 状态
- 更新时间
- 操作

操作：

- 查看详情
- 取消待执行任务

详情：

- 赔率回填摘要
- 候选诊断
- 批量记录结果
- Bark 中发送的信心模拟推荐组
- Bark 标题、正文或分片消息
- 任务错误
- Bark 错误或 HTTP 状态码

## 测试计划

后端测试：

- 创建任务时目标时间段没有本地赛程会被拒绝。
- 创建任务时触发时间已过去会被拒绝。
- 创建任务时重复 `pending` 或 `running` 任务会被拒绝。
- `pending` 任务到点后会执行。
- 到点任务超过宽限时间后变为 `missed`。
- 多个到点任务串行执行。
- 有 `running` 任务时不会启动新任务。
- 因排队等待超过宽限时间的任务会变为 `missed`。
- 单场赔率回填失败不会导致整个任务失败。
- 候选生成异常会导致任务 `failed`。
- 无候选任务会 `success`，并发送无候选 Bark 文本。
- 重复纸面记录会被跳过并记录原因。
- Bark 失败时任务仍为 `success`，但 `notification_status = failed`。
- Bark 未配置时任务仍为 `success`，但 `notification_status = not_configured`。
- Bark 内容包含所有受影响的信心模拟推荐组，并使用和 `build_paper_confidence_workspace(...)` 一致的 `confidence_score` 和 `suggested_stake_units`。
- 只有 `pending` 任务可以取消。

前端测试：

- 比赛列表页自动任务创建弹窗可渲染。
- 任务创建成功后显示计划执行提示。
- 目标时间段无本地赛程时显示校验错误。
- 自动任务页展示任务状态和 Bark 状态。
- `pending` 任务显示取消操作。
- `running`、`success`、`failed` 任务不显示取消操作。
- 详情页展示赔率、记录、信心模拟和 Bark 错误。

## 实施顺序

建议分小步实现：

1. 数据模型、任务仓储/服务和测试。
2. Bark 通知器和消息格式化器，并覆盖信心模拟推荐组一致性测试。
3. 任务执行服务和调度器。
4. Web API。
5. 比赛列表页创建弹窗。
6. 自动任务页。
