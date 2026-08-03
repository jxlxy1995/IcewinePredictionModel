# 推荐快照回顾 All 来源模式设计

日期：2026-08-04

## 背景

推荐快照回顾页当前要求选择一个明确的 `snapshot_source`，默认值为
`historical_backfill`。这不方便查看正常运行窗口内 `automation` 与少量
`manual_record` 的合并表现，也容易让使用者把空的历史回填页面误解为该
窗口没有快照。

本功能为来源下拉框增加 `All / 全部来源` 模式。All 模式在一次查询中
汇总时间窗口内的全部实际来源，同时对重复 group key 做确定性去重，并
公开来源分布和去重数量，便于用户及后续智能体理解合并口径。

## 目标

- 来源下拉框增加 `全部来源（All）`。
- API 支持显式 `snapshot_source=all`。
- All 模式汇总当前及未来出现的全部快照来源。
- All 模式按 `group_key` 去重，避免真实运行来源与历史回填重叠时重复计数。
- API 返回去重元数据和去重后的来源分布。
- 页面展示按来源统计，方便核对合并组成。
- 保持单一来源查询、默认来源和 CLI 现有口径不变。

## 非目标

- 不修改策略、置信度、建议手数、stake cap 或结算逻辑。
- 不写入或回填任何快照。
- 不改变 CLI `records snapshot-report` 在未传 `--source` 时的现有行为。
- 不把页面默认来源改为 All；本轮仅增加可选模式。
- 不为历史记录重建或修正 group key。

## 方案比较

### 方案 A：后端原生 All 模式，服务层去重

前端传 `snapshot_source=all`，后端查询所有来源，在快照回顾服务层按
group key 去重后统一生成总览、分桶和样本列表。

优点：统计逻辑只有一个事实来源；未来新增来源会自动纳入；去重规则可测试、
可供 Web 和后续调用者复用；页面只需一次请求。

缺点：需要扩展服务返回结构和 API 类型。

这是采用方案。

### 方案 B：前端并行请求每个来源后合并

优点：后端改动较少。

缺点：前端必须提前知道全部来源，并重复实现收益汇总和去重；新来源无法自动
纳入；样本排序和 ROI 口径容易与后端漂移。因此不采用。

### 方案 C：省略 `snapshot_source` 表示 All

优点：URL 较短。

缺点：当前省略参数表示默认 `historical_backfill`，改变语义会破坏已有调用和
页面默认行为。因此不采用。

## API 契约

请求示例：

```text
GET /api/paper-snapshot-review?from_date=2026-07-01T00:00:00&to_date=2026-07-31T23:59:59&snapshot_source=all
```

规则：

- `snapshot_source=all` 映射为服务层的无来源过滤查询。
- 未传 `snapshot_source` 时仍默认 `historical_backfill`。
- 传具体来源时继续只查询该来源，不执行 group key 去重。
- `filters.snapshot_source` 原样返回 `all`，便于客户端保持选择状态。
- 时间过滤继续使用代表记录的 `kickoff_time`。
- `snapshot_version` 过滤保持不变。

响应在现有结构上增加：

```json
{
  "deduplication": {
    "applied": true,
    "input_group_count": 290,
    "selected_group_count": 288,
    "excluded_group_count": 2
  },
  "groups": {
    "by_snapshot_source": [
      {
        "group_name": "automation",
        "group_count": 282
      },
      {
        "group_name": "manual_record",
        "group_count": 6
      }
    ]
  }
}
```

所有来源分组使用与其他分组相同的完整 summary 字段。来源分布基于去重后
实际入选的快照，因此其组数之和等于 `summary.group_count`。

具体来源模式也返回 `deduplication`，但 `applied=false`，三个计数字段相等；
这让响应类型稳定，也明确表示该模式没有做跨来源去重。

## 去重规则

All 模式对过滤后的快照按 `group_key` 只保留一条。选择顺序从高到低为：

1. `automation`
2. `manual_record`
3. 除 `historical_backfill` 外的其他未来来源
4. `historical_backfill`

同一优先级内依次选择：

1. `created_at` 较新的快照
2. `id` 较大的快照

设计理由：正常运行以 automation 为主，manual_record 是补充，二者都比
历史重放更接近真实执行时状态；未来未知来源不应被历史回填覆盖。同一来源
重复时，较新快照更能代表最终冻结的信号集合。

去重只影响 All 模式。具体来源模式保持当前逐快照统计行为，以避免悄然改变
既有 API 和 CLI 语义。

## 服务结构

`SnapshotReviewWorkspace` 增加：

- `by_snapshot_source`
- `deduplication`

新增内部去重单元，输入过滤后的快照列表，输出：

- 入选快照列表
- 输入数量
- 入选数量
- 排除数量

`build_snapshot_review_workspace(...)` 接受可空 `snapshot_source`：

- 具体来源：沿用当前报告结果，`applied=false`。
- `None`：查询所有来源，执行去重，再基于入选快照重新计算全部 summary、
  buckets 和 samples。

CLI 继续直接调用 `build_snapshot_report(...)`，不启用这项 Web 回顾去重。

## 前端设计

来源选项集中定义在 `paperSnapshotReviewWorkspace.ts`，避免 JSX 中散落硬编码：

- `全部来源（All）`，值为 `all`
- `historical_backfill`
- `manual_record`
- `automation`

默认过滤器继续使用 `historical_backfill`。选择 All 后，现有 API client 会显式
发送 `snapshot_source=all`。

页面增加：

- “按来源”分组表，展示去重后各来源的组数、收益和 ROI。
- All 模式下的“去重排除”指标卡，值为 `excluded_group_count`；具体来源模式
  不显示该卡，避免无意义的固定 0。
- “按信号数”表与“按来源”表并列，复用后端已经返回但当前未展示的
  `by_signal_count`。

不增加解释性横幅或新的操作流程；All 仍通过现有刷新按钮应用。

## 错误与兼容处理

- 未识别的具体来源仍按普通来源字符串过滤，可自然返回空结果。
- 仅精确小写值 `all` 作为保留查询值解释；其他字符串继续按普通来源过滤，
  不增加别名或大小写转换。
- 空窗口返回 0 组、空来源分布及全 0 去重计数。
- 现有 mock workspace 和 TypeScript 类型补齐新增字段，避免 API 不可用时页面
  fallback 失效。
- API cache key 继续包含原始 `snapshot_source`，All 与具体来源不会互相污染。

## 测试策略

### 后端服务测试

- All 模式合并不同 group key 的 automation 和 manual_record。
- 相同 group key 同时存在 automation、manual_record、未知来源和
  historical_backfill 时选择 automation。
- 没有 automation 时选择 manual_record；没有两个真实来源时选择未知来源而
  不是 historical_backfill。
- 同一来源相同 group key 选择较新的快照，再以较大 ID 作为最终 tie-break。
- 去重后来源分组之和等于 summary 组数。
- 具体来源模式不去重且 `applied=false`。

### Web API 测试

- `snapshot_source=all` 返回合并、去重后的 summary。
- payload 返回 `filters.snapshot_source=all`、`deduplication` 和
  `groups.by_snapshot_source`。
- 不传来源时仍为 `historical_backfill`。

### 前端测试

- 来源选项包含 All 及三个现有来源。
- 默认来源仍为 `historical_backfill`。
- API client 对 All 显式生成 `snapshot_source=all`。
- All workspace 显示去重排除卡；具体来源 workspace 不显示。
- TypeScript 构建和现有前端测试保持通过。

## 验收标准

- 用户可在来源下拉框选择 `全部来源（All）` 并刷新。
- 2026 年 7 月真实本地数据的 All 结果在无来源交叉重复时等于 automation 与
  manual_record 的可信合计。
- 人为构造跨来源相同 group key 时只统计一次，并符合来源优先级。
- 页面能直接看到去重后的来源分布和被排除数量。
- 具体来源查询、默认页面行为和 CLI 报告无回归。
