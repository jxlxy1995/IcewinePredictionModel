# 2026-07-15 纸面推荐快照半月回顾

回顾执行日期：2026-07-16

## 回顾目的

本次为原定 2026-07-15 的轻量半月回顾。由于当天未执行，顺延至
2026-07-16。回顾只分析真实本地数据，不修改策略参数、权重、模型或
生产逻辑。

## 数据窗口与口径

- 比赛窗口：北京时间 `2026-07-01T00:00:00` 至
  `2026-07-16T23:59:59`。
- 时间轴：代表纸面记录的比赛 `kickoff_time`，不是快照 `created_at`。
- 快照版本：`paper_confidence_v1`。
- 查询入口：Web API `/api/paper-snapshot-review` 与 CLI
  `records snapshot-report`，两边结果一致。
- 正常运行来源：以 `automation` 为主，少量 `manual_record` 为补充。
- `historical_backfill` 在本窗口为 0 组，不能作为本次主口径。

后续新运行窗口不应为了填充默认页面而重复生成 `historical_backfill`。
应分别报告 `automation`、`manual_record`，确认来源间无重复后，再给出
合并参考值。

## 来源分布与总览

| 来源 | 组数 | 已结算 | Pending | Flat ROI | Weighted ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| automation | 100 | 100 | 0 | -17.07% | -14.64% |
| manual_record | 2 | 2 | 0 | +101.00% | +101.27% |
| historical_backfill | 0 | 0 | 0 | 0 | 0 |
| 实际来源合计 | 102 | 102 | 0 | -14.75% | -11.50% |

两条 `manual_record` 来自 2026-07-14 同一场瑞典超比赛，分别为亚盘主队
方向和大小球小球方向，两组均盈利。其样本量不足，不能用来抵消或否定
`automation` 的主要趋势。

102 个快照对应 102 个唯一 group key，`automation` 与 `manual_record`
之间没有重复组。

## 与上一阶段基准对比

2026-05-01 至 2026-06-24 的 `historical_backfill` 阶段基准：

- group_count：850
- settled_groups：850
- pending_groups：0
- flat ROI：+25.71%
- weighted ROI：+27.50%

本次 `automation` 的 flat ROI 为 -17.07%，weighted ROI 为 -14.64%，
相较阶段基准出现明显反转。不过两者来源性质、时间长度和比赛分布不同，
本次结果应视为预警，不能仅凭半月窗口认定长期策略失效。

## 主要分组观察

### 市场与方向

- 亚盘：40 组，weighted ROI -11.77%。
- 大小球：60 组，weighted ROI -17.91%，是更弱的市场。
- 亚盘客队方向：36 组，weighted ROI -7.02%。
- 亚盘主队方向：4 组，weighted ROI -48.75%，样本过少。
- 大球：23 组，weighted ROI -28.73%。
- 小球：37 组，weighted ROI -15.11%。

### 置信度与建议手数

- `85-89`：10 组，weighted profit -7.530，weighted ROI -50.20%。
- `90-94`：4 组，weighted profit +4.340，weighted ROI +57.87%，样本很小。
- 置信度不呈稳定单调关系。置信度 `>=80` 共 26 组，其中 16 组产生
  负收益，合计 weighted ROI 约 -12.27%。
- `1.50` 手：32 组，weighted profit -15.202，weighted ROI -31.67%，
  是本窗口最主要拖累。
- `2.00` 手：3 组，weighted profit +5.840，weighted ROI +97.33%，
  不足以支持提高高建议手数。

### 盘口桶

- 亚盘 `pickem`：3 组，weighted ROI +21.84%，未见异常亏损。
- 大小球 `mid_2.50`：14 组，flat ROI -16.79%，但 weighted ROI
  +20.40%。该差异主要与低手数和 0 手观察组有关。
- 大小球 `low_<=2.25`：13 组，weighted ROI -25.54%。
- 大小球 `mid_2.75`：10 组，weighted ROI -26.41%。
- 大小球 `high_>=3.00`：23 组，weighted ROI -10.56%。
- 亚盘 `away_underdog`：18 组，weighted ROI -21.36%。

### Signal family 与信号数量

- `total_goals_hgb`：23 组，weighted profit -7.024，weighted ROI
  -26.01%，是当前最需观察的 family。
- `total_goals_distribution_hgb`：37 组，weighted ROI -6.54%。
- `asian_away_hgb`：36 组，weighted ROI -7.02%。
- `asian_home_hgb`：4 组，weighted ROI -48.75%，样本不足。
- 单信号组：78 组，weighted ROI -20.76%。
- 双信号组：22 组，weighted ROI -2.93%，相对稳定。

`total_goals_hgb`、低线和 2.75 线位在上一阶段仍为正收益，本次属于
短窗口反转，暂不能称为长期持续失效。

### 联赛

主要正贡献：

- 世界杯：20 组，weighted profit +2.537。
- 韩K联：8 组，weighted profit +2.174。
- 瑞典超：10 组，weighted profit +2.046。

主要负贡献：

- 冰岛超：5 组，weighted profit -4.350，weighted ROI -64.44%。
- 爱甲：8 组，weighted profit -4.312，weighted ROI -52.27%。
- 芬甲：8 组，weighted profit -3.720，weighted ROI -55.11%。
- 中超：8 组，weighted profit -2.750，weighted ROI -42.31%。
- 芬超：8 组，weighted profit -2.695，weighted ROI -38.50%。

冰岛超上一阶段 weighted ROI 已为 -34.12%，本次继续为负，是少数
呈现持续弱势的项目，但两期样本合计仍只有 11 组。

## 时间分布与 0 手影响

- 2026-07-01 至 2026-07-08：56 组，weighted ROI -6.26%。
- 2026-07-09 至 2026-07-16：44 组，weighted ROI -26.61%。
- 其中 2026-07-09 至 2026-07-12：38 组，weighted ROI -26.88%，
  亏损存在明显时间聚集。
- 2026-07-05 至 2026-07-08：19 组，weighted ROI +13.44%。

`automation` 有 10 个 0 手组，flat profit 合计 -4.370。包含它们时
flat ROI 为 -17.07%；剔除后非 0 手组 flat ROI 约为 -14.11%。0 手组
使 flat ROI 额外恶化约 2.96 个百分点，但不会影响 weighted ROI。

## 数据完整性检查

未发现结构性数据异常：

- 102 个快照 ID 和 group key 均唯一。
- 无来源间重复组。
- 无缺失代表记录或盘口桶。
- 无无效赔率、负建议手数。
- 无已结算但缺失收益的记录。
- 全部 102 组已结算，pending 为 0。

`historical_backfill=0` 是来源覆盖和默认页面口径问题，不是数据损坏。

## 本次决策

- 不调整策略参数、权重、模型或生产逻辑。
- 不提高高建议手数，也不根据 3 个 2.00 手盈利样本扩大使用范围。
- 保持当前设置，将本次结果作为明确预警继续观察。
- 重点跟踪 1.50 手、85-89 置信度、`total_goals_hgb`、大小球低线和
  2.75 线、单信号组，以及冰岛超等持续弱势联赛。

## 下一次回顾

下一次正式月度回顾日期：2026-08-01。

正式窗口使用完整自然月：北京时间 `2026-07-01T00:00:00` 至
`2026-07-31T23:59:59`。除完整月度结果外，还应拆分比较：

- 2026-07-01 至 2026-07-16
- 2026-07-17 至 2026-07-31
- 2026-07-09 至 2026-07-12 的集中回撤与后续表现

