# Dixon-Coles 与统一模型接口设计

创建时间：2026-05-25 北京时间

## 一、目标

本阶段补充比分概率层的模型能力，为后续多模型复合驱动打基础。

本阶段完成两件事：

- 建立统一的比分模型预测入口，让现有基础模型、球队强度模型、联赛级球队强度模型和新增 Dixon-Coles 模型都能输出同一种比分概率分布。
- 新增 Dixon-Coles 进球模型，用低比分相关性参数修正泊松比分分布，支持后续亚盘和大小球概率计算。

本阶段不改变赔率回填规则，不改变训练样本抽样规则，不把 Dixon-Coles 自动设为生产推荐模型。

## 二、设计原则

### 1. 不依赖未提交数据口径

Dixon-Coles 训练只使用 `TrainingSample` 中已经存在的赛果字段：

- `home_score`
- `away_score`
- `time_decay_weight`

它不读取 `odds_snapshots` 或 `historical_odds_snapshots`，避免和并行进行的赔率回填口径冲突。

### 2. 模型输出统一为比分概率分布

系统已有 `GoalDistributionPrediction`，可以表达：

- 主队期望进球
- 客队期望进球
- 比分概率矩阵
- 胜平负概率

本阶段把它作为比分模型的统一输出。推荐层和后续回测层只需要消费比分概率分布，不需要知道底层模型是泊松、球队强度还是 Dixon-Coles。

### 3. 保持现有行为稳定

现有 `recommendations model-preview` 和 `recommendations record` 继续默认使用联赛级球队强度模型。

Dixon-Coles 先通过独立 CLI 命令训练和评估，供工程验证；后续是否接入默认推荐由回测结果决定。

## 三、模块设计

### 1. `goal_distribution_service`

新增一个公开构造函数，用于从外部模型生成的比分概率矩阵构建 `GoalDistributionPrediction`。

职责：

- 接收未归一化或已归一化的比分概率。
- 统一归一化到总和 `1.0000`。
- 计算胜平负概率。
- 保持现有泊松分布构造函数不变。

### 2. `score_model_service`

新增统一模型入口。

职责：

- 定义 `ScoreModelContext`，封装联赛名、主队名、客队名。
- 提供 `predict_goal_distribution_from_model(model, context)`。
- 适配现有模型：
  - `BaselineResultModel`
  - `TeamStrengthGoalModel`
  - `LeagueTeamStrengthGoalModel`
  - 任何提供 `predict_goal_distribution()` 方法的模型，例如 Dixon-Coles。

这个服务只做模型适配，不负责训练。

### 3. `dixon_coles_model_service`

新增 Dixon-Coles 模型与训练函数。

职责：

- 定义 `DixonColesGoalModel`。
- 使用样本的加权平均进球训练基础主客期望进球。
- 使用 `scipy.optimize.minimize_scalar` 拟合低比分相关参数 `rho`。
- 输出经过 Dixon-Coles 修正的比分概率分布。

Dixon-Coles 修正只作用于低比分：

- `0-0`
- `0-1`
- `1-0`
- `1-1`

其他比分保持泊松独立分布。

## 四、推荐层接入

推荐层改为通过统一模型入口取得比分概率分布，再转换为现有 `ScoreProbabilityGrid` 供亚盘和大小球概率计算。

这样做的好处：

- 现有基础模型输出不变。
- Dixon-Coles 的低比分修正可以进入亚盘和大小球概率计算。
- 后续新增负二项、Elo 融合模型时，不需要再改推荐层核心计算。

## 五、CLI 设计

新增模型训练命令：

```powershell
icewine models train-dixon-coles --limit 1000
```

输出内容：

- 训练样本数
- 主队期望进球
- 客队期望进球
- Dixon-Coles `rho`
- 胜平负概率

现有 `models train-baseline` 保持不变。

## 六、依赖策略

本阶段最多引入 `scipy`。

`scipy` 只用于 `rho` 的一维有界优化，不引入更重的机器学习框架。后续如果加入 LightGBM、XGBoost 或 CatBoost，需要单独设计和回测。

## 七、测试策略

测试覆盖以下行为：

- 从比分概率矩阵构建的 `GoalDistributionPrediction` 会归一化。
- 统一模型入口能适配现有基础模型、球队强度模型和联赛级球队强度模型。
- Dixon-Coles 模型会修正低比分概率，且比分概率总和为 `1.0000`。
- Dixon-Coles 训练会返回有界 `rho` 和可用的比分概率分布。
- 推荐层可以消费 Dixon-Coles 模型。
- CLI 可以输出 Dixon-Coles 训练结果。

## 八、明确不做

本阶段不做以下内容：

- 不持久化模型参数。
- 不新增模型运行表或预测结果表。
- 不修改历史赔率抽样规则。
- 不修改默认推荐模型。
- 不声明收益提升。
- 不实现 ensemble 或自动模型上线。

这些内容需要在赔率数据回填口径稳定、回测样本足够后再设计。
