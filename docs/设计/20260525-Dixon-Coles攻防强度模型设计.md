# Dixon-Coles 攻防强度模型设计

创建时间：2026-05-25 北京时间

## 一、目标

本阶段在已有 Dixon-Coles 全局均值模型之上，新增球队攻防强度版本。

已有模型使用全局主客期望进球和 `rho` 修正低比分，适合作为 baseline。本阶段模型进一步学习每支球队的进攻强度、防守强度和主场优势，使同一个比分概率模型可以区分强弱队对阵。

## 二、输入与边界

输入仍然只使用 `TrainingSample` 中已经存在的赛果字段：

- `home_team_name`
- `away_team_name`
- `home_score`
- `away_score`
- `time_decay_weight`

本阶段不读取赔率快照，不使用盘口走势，不修改推荐默认模型。

## 三、模型形式

模型保存：

- 主队基础进球截距。
- 客队基础进球截距。
- 主场优势。
- 每队进攻参数。
- 每队防守参数。
- Dixon-Coles 低比分相关参数 `rho`。

预测某场比赛时：

```text
home_lambda = exp(home_intercept + home_advantage + home_attack - away_defense)
away_lambda = exp(away_intercept + away_attack - home_defense)
```

然后按 Dixon-Coles 规则修正低比分：

- `0-0`
- `0-1`
- `1-0`
- `1-1`

未见过的球队使用中性攻防参数 `0`，即只使用基础截距和主场优势。

## 四、训练策略

使用 `scipy.optimize.minimize` 最小化加权负对数似然。

参数边界：

- 攻击、防守参数限制在 `[-3, 3]`。
- 主场优势限制在 `[-1, 1]`。
- `rho` 限制在 `[-0.25, 0.25]`。

为减少参数漂移，目标函数加入轻量 L2 正则项。第一版不做模型持久化，也不做跨联赛分模型。

## 五、工程接入

新增模型类：

```python
DixonColesAttackDefenseModel
```

新增训练函数：

```python
train_dixon_coles_attack_defense_model(samples)
```

新增预测方法：

```python
predict_match_goal_distribution(home_team_name, away_team_name)
```

统一模型入口 `predict_goal_distribution_from_model` 会识别这个方法，并要求调用方提供主客队上下文。

## 六、CLI

新增命令：

```powershell
icewine models train-dixon-coles-attack-defense --limit 1000
```

输出：

- 训练样本数
- 球队数
- 主场优势
- `rho`
- 主队基础期望进球
- 客队基础期望进球

## 七、明确不做

本阶段不做：

- 不接入赔率特征。
- 不切换默认推荐模型。
- 不做联赛级 Dixon-Coles 子模型。
- 不持久化模型参数。
- 不声明收益提升。

后续如果继续做模型本体，优先方向是 Skellam 净胜球模型或负二项进球模型。
