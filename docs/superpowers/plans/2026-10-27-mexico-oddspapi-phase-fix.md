# 墨西超 OddsPapi 阶段映射修复

> **For agentic workers:** 使用 executing-plans 在当前会话完成；用户已要求开始处理故障。

**Goal:** 恢复墨西超 Apertura 的赛程匹配与赔率采集，同时保留 Clausura。

**Architecture:** 在 odds_source_match_service 增加共享赛事解析函数，优先使用 league_round 的 Apertura/Clausura；缺失阶段时按墨西哥当地比赛月份（7–12 月 Apertura，1–6 月 Clausura）回退。主同步、probe、diagnostics 与匹配校验使用同一函数。保留原静态字典作为默认映射及白名单判定。

**Tech Stack:** Python、SQLAlchemy、pytest、OddsPapi v4。

**Spec:** 本会话用户授权修复墨西超。官方 tournaments 已确认 27464=liga-mx-apertura、27466=liga-mx-clausura；近期 fixtures 已在 27464 下验证三场比赛。

## 约束与复核重点

- 不改变其他联赛映射、模型或推荐规则；不修改全局网络代理设置。
- 阶段字段优先于月份，以兼容延期比赛；统一考虑数据库无时区北京时间及 aware datetime。
- 查询与匹配校验必须一致；旧 Clausura 仍使用 27466。
- 已有 unavailable 记录需要显式 match_ids 重试；不全局清除失败状态。
- 保留已有其他来源赔率，在线请求设预算并遵守间隔。

## 任务

- [x] 为两个阶段、跨月延期、缺失阶段、其他联赛与 probe/diagnostics 添加回归测试，确认修复前失败。
- [x] 实现共享解析，接入主同步、probe、匹配校验与 diagnostics。
- [x] 运行相关测试并检查差异。
- [x] 实际恢复最近一轮 9 场，并将其余错误映射造成的终止状态恢复为可重试；历史全量补采不在本轮启动。
- [x] 保存实际结果和剩余限制。

## 执行记录

- 修复前工作区已有 config/display_names.yaml、临时目录与交接报告变更；不覆盖用户变更。
- 网络诊断：强制直连遇 ConnectionReset，默认 requests 会话可访问但间歇超时/SSL 错误；仅诊断/恢复脚本使用默认会话。
- 初次含目录响应落盘的升级请求被自动审批拒绝；去除落盘后的只读请求获准并成功。
- 新增 14 项测试修复前 7 失败、7 通过，失败均为 Apertura 固定走 Clausura；修复后 14 项通过。
- 相关完整测试 86 通过、1 失败。失败为已有 preserves_execution_timepoints_after_sampling（期待 3，实际 4）；在内存加载 git HEAD 原代码后重跑同样失败，确定为既有问题。
- 纳入 batch backfill 后，排除上述已证实基线问题的测试结果为 113 passed, 1 deselected；git diff --check 通过。
- 请求独立审查两次均未取得有效审查内容，改为逐项自行检查调用覆盖、非墨西超分支、阶段/时区与恢复数据；不声称已通过独立审查。
- 最近一轮 9 场恢复 1726 条 OddsPapi 主表赔率；原 The Odds API 378 条保留；9 场均达到综合来源 18/18 时间点覆盖。
- 对 70 条旧 Apertura 错误映射 404 记录保存备份后改为 fixture_lookup_failed，使其可重试；保留原错误信息，不删除赔率。旧失败记录不会再被 terminal 状态永久跳过。
- 仅重载网页后端，核实无活动同步/自动任务后启动新进程 PID 30548，health=200；前端与独立采集进程未停止。
