# 2026-08-26 赔率源切换验证

## 结论

共享比赛赔率同步顺序调整为：

1. `oddspapi / pinnacle`
2. `the_odds_api / pinnacle`
3. `zqcf918 / pinnacle`

`oddspapi / sbobet` 不再由共享同步链路调用，也不再作为可信历史赔率来源。数据库中已有 SBOBet 快照保留用于审计，但不会被模型选源使用。

## Oddspapi 可用性验证

测试时间窗为北京时间 `2026-08-25 12:00` 至 `2026-08-26 12:00`，白名单联赛排除欧冠、欧联和欧协联等杯赛。

首轮 7 个联赛各取 1 场，真实请求 `15` 次，`7/7` fixture 匹配成功，`7/7` 历史赔率请求成功，写入 `2,124` 条标准快照作为本地验证样本。每场均有亚盘、大小球、胜平负。

剩余 8 场在复制的 SQLite 数据库上顺序测试，不污染正式库：`7/8` 成功，`1` 场因 `ReadTimeout` 失败，没有出现 404 或 key/budget 错误。成功样本仍同时覆盖三类盘口，通常约 `302` 条标准快照；部分较晚或数据较稀疏的比赛返回 44-48 条，但市场请求正常。

## 别名

为低置信度样本补充：

- `Tigre` -> `CA Tigre`
- `Atletico Paranaense` -> `Athletico Paranaense`

这两个别名用于降低阿根廷、巴西联赛的球队名匹配风险。后续扩大批次时仍需关注低于 `0.75` 的匹配记录。

## 风险与操作建议

免费版 key 已能完成小批量测试，但连续历史赔率请求存在偶发超时；生产 worker 继续使用 safe 模式、低并发和请求冷却。30 秒数据延迟不影响本项目的历史快照及赛前执行时间点。

验证命令：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_odds_provider_selection_service.py tests/test_match_odds_sync_service.py tests/test_oddspapi_sync_runner.py tests/test_the_odds_api_sync_runner.py -q
```

结果：`125 passed`。
