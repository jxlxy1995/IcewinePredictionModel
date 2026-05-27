# OddsPapi 夜间回填规则

这份备忘用于大段空闲时间的历史赔率回填。以后用户只要说类似：

- `按夜间回填规则跑 4h`
- `按夜间回填规则跑 6h`
- `按夜间回填规则跑 8h`
- `先探测未回填联赛，然后夜间 safe 回填`

就按本文执行。

## 目标

在不需要用户盯着命令行的情况下，尽量稳定地回填 OddsPapi 历史赔率。夜间优先稳定，不追求极限并发。

## 总原则

- 大段时间默认使用 `safe` 模式，也就是单 worker。
- 不开多个独立 worker 进程同时请求 OddsPapi。
- 只有在用户明确要求加速、且当前 API 状态稳定时，才考虑 `balanced`。
- 新联赛必须先做 tournament 映射探测和 fixture 小样本诊断，通过后再加入长跑批次。
- 已有 `empty`、`unavailable`、`unmatched` 的终止状态默认不重复请求，除非刚补了映射或别名并明确需要重置。
- 法甲这类重要联赛如果出现 404，先查 tournament 映射，不要直接判断为缺数据。

## 夜间启动前检查

1. 查看当前 worker 是否还在跑：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 120
```

2. 如果旧 worker 还在跑，先判断是否应该停：

- 如果旧 worker 是用户明确要继续跑的，不停。
- 如果旧 worker 只是临时补漏，且要启动更重要的大批次，可以停掉。
- 停进程前先记录 PID 和当前进度。

3. 停 worker：

```powershell
Stop-Process -Id <PID> -Force -ErrorAction SilentlyContinue
```

## 探测未回填联赛

### 1. 查本地候选规模

优先查看 `2026-01-15` 后还有多少完赛比赛没有 OddsPapi 快照。当前 OddsPapi 历史数据主要从 2026 年 1 月附近开始稳定，默认从 `2026-01-15` 跑。

候选联赛要满足：

- 本地已有 API-Football 完赛数据。
- 还没有大规模历史赔率快照。
- 在 OddsPapi tournament 列表中能找到明确对应项。

### 2. 查询 OddsPapi tournament

使用 OddsPapi `tournaments` 接口筛选 `sportId=10`。重点看：

- `tournamentId`
- `tournamentSlug`
- `tournamentName`
- `categorySlug`
- `categoryName`

映射必须按国家和联赛名同时确认。不能只看联赛名，比如 `Ligue 1` 有多个国家同名联赛。

已确认的映射示例：

```text
法甲 Ligue 1 France id=61 -> OddsPapi tournamentId=34
比甲 Jupiler Pro League Belgium id=144 -> OddsPapi tournamentId=38
奥甲 Bundesliga Austria id=218 -> OddsPapi tournamentId=45
瑞士超 Super League Switzerland id=207 -> OddsPapi tournamentId=215
澳超 A-League Australia id=188 -> OddsPapi tournamentId=136
苏超 Premiership Scotland id=179 -> OddsPapi tournamentId=36
```

### 3. fixture 小样本诊断

每个新映射联赛先跑小样本诊断：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-diagnose-fixtures `
  --season 2025 `
  --league-ids <LEAGUE_ID> `
  --from-date 2026-01-15 `
  --max-matches 8 `
  --request-budget 20 `
  --timeout-seconds 25
```

诊断结果判断：

- `matched > 0`：可加入回填批次。
- `manual_review > 0`：先看候选队名，补别名后再跑。
- `api_error` 多且是 `404`：优先检查 tournament 映射是否错。
- `api_error` 是 `429`：先冷却，稍后重试，不要立刻判断映射错。
- `diagnosed=0`：通常是没有映射、没有候选、或该批已被终止状态跳过，需要查原因。

## 写入映射

映射写在：

```text
src/icewine_prediction/oddspapi_sync_runner.py
```

变量：

```python
API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS
```

新增映射后，必须补测试：

```text
tests/test_oddspapi_sync_runner.py
```

至少验证关键联赛 ID 映射值。

提交前运行：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_oddspapi_sync_runner.py::test_api_football_league_mappings_include_new_sleep_backfill_targets -q
git diff --check
```

## safe 夜间回填命令

按用户指定时长换算 `hard-timeout-seconds`：

```text
4h = 14400
6h = 21600
8h = 28800
```

推荐命令模板：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-start `
  --season 2025 `
  --mode safe `
  --chunk-size 1 `
  --request-budget-per-league 1200 `
  --timeout-seconds 25 `
  --max-snapshots-per-match 100 `
  --max-rounds-per-league 240 `
  --stop-after-empty-matches 12 `
  --stop-after-failed-rounds 5 `
  --round-timeout-seconds 180 `
  --historical-odds-cooldown-seconds 7.5 `
  --hard-timeout-seconds <SECONDS> `
  --log-dir logs/odds `
  --league-ids <COMMA_SEPARATED_LEAGUE_IDS> `
  --from-date 2026-01-15 `
  --notify-on-complete
```

说明：

- `safe`：单 worker，适合夜间稳定回填。
- `chunk-size=1`：每轮处理一场，日志和状态更清楚。
- `max-rounds-per-league=240`：单联赛最多尝试 240 轮；在 `chunk-size=1` 时近似最多 240 场候选。
- `stop-after-empty-matches=12`：连续空数据达到阈值后切下一个联赛。
- `stop-after-failed-rounds=5`：连续失败轮次达到阈值后切下一个联赛。
- `historical-odds-cooldown-seconds=7.5`：比官方 5 秒更保守，降低 429。

## 联赛切换逻辑

在 `safe` 模式下，worker 会按联赛顺序依次跑：

1. 当前联赛一场一场回填。
2. 已有赔率快照的比赛跳过。
3. 能写入快照则继续下一场。
4. `empty`、`unavailable`、`unmatched` 会记录终止状态。
5. 连续空数据达到阈值，切到下一个联赛。
6. 连续失败达到阈值，切到下一个联赛。
7. 当前联赛没有候选比赛，切到下一个联赛。

## 状态检查

PowerShell：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 120
```

Git Bash：

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 /c/ProgramData/anaconda3/python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 120
```

重点看：

- `status=running` / `status=stopped`
- `mode=safe`
- `workers=1`
- 当前联赛、round、processed、snapshots、failed、requests
- `停止原因`
- `最近日志`

## 早晨收尾

醒来后先看 worker 状态，再统计覆盖率和异常状态：

- `success`
- `empty`
- `unavailable`
- `unmatched`
- `failed`
- `no_source`

处理顺序：

1. 如果 `unmatched` 多，先做别名诊断和别名补充。
2. 如果 `failed` 多，查是否为 429、网络错误、还是 fixture/market/historical-odds 单点错误。
3. 如果 `empty/unavailable` 集中在 2026-01-15 附近，通常视为 OddsPapi 早期历史数据缺口。
4. 如果 `no_source` 很多，说明 worker 提前切换或达到限制，可以再小批量补跑。

## 何时使用 balanced

只有在这些条件同时满足时才考虑 `balanced`：

- 用户明确希望加速。
- 当前 API 没有明显 429。
- 已经验证该批联赛映射和别名稳定。
- 用户能在旁边盯 10 到 20 分钟。

夜里无人值守默认不用 `balanced`。
