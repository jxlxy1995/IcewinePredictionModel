# Dixon-Coles 与统一模型接口实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增统一比分模型预测入口，并实现 Dixon-Coles 进球模型，供后续多模型复合推荐使用。

**Architecture:** 以 `GoalDistributionPrediction` 作为统一比分模型输出。新增 `score_model_service.py` 适配现有模型和新增模型；新增 `dixon_coles_model_service.py` 负责 Dixon-Coles 参数拟合和比分概率生成；推荐层通过统一入口消费模型分布。

**Tech Stack:** Python 3.11+、Decimal、scipy、pytest、Typer、SQLAlchemy、Asia/Shanghai 时间。

---

### Task 1: 比分概率分布公共构造函数

**Files:**
- Modify: `src/icewine_prediction/goal_distribution_service.py`
- Test: `tests/test_goal_distribution_service.py`

- [ ] **Step 1: Write the failing test**

Add a test that calls `build_goal_distribution_prediction_from_scores` with raw score probabilities that do not sum to one.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goal_distribution_service.py::test_goal_distribution_prediction_from_scores_normalizes_probabilities -q`

Expected: FAIL because `build_goal_distribution_prediction_from_scores` is not defined.

- [ ] **Step 3: Write minimal implementation**

Add a public function that normalizes score probabilities and delegates to the existing prediction builder.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goal_distribution_service.py::test_goal_distribution_prediction_from_scores_normalizes_probabilities -q`

Expected: PASS.

### Task 2: 统一比分模型预测入口

**Files:**
- Create: `src/icewine_prediction/score_model_service.py`
- Test: `tests/test_score_model_service.py`

- [ ] **Step 1: Write failing tests**

Cover:

- `BaselineResultModel` can be predicted without context.
- `TeamStrengthGoalModel` requires home and away team names.
- `LeagueTeamStrengthGoalModel` uses league context.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_score_model_service.py -q`

Expected: FAIL because `score_model_service.py` is missing.

- [ ] **Step 3: Write minimal implementation**

Add:

- `ScoreModelContext`
- `predict_goal_distribution_from_model(model, context=None)`

The function should return `GoalDistributionPrediction`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_score_model_service.py -q`

Expected: PASS.

### Task 3: Dixon-Coles 模型

**Files:**
- Create: `src/icewine_prediction/dixon_coles_model_service.py`
- Modify: `pyproject.toml`
- Test: `tests/test_dixon_coles_model_service.py`

- [ ] **Step 1: Write failing tests**

Cover:

- Low score probabilities are adjusted by `rho`.
- Score probabilities sum to `1.0000`.
- Training returns a model with bounded `rho`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dixon_coles_model_service.py -q`

Expected: FAIL because `dixon_coles_model_service.py` is missing.

- [ ] **Step 3: Write minimal implementation**

Add:

- `DixonColesGoalModel`
- `train_dixon_coles_goal_model(samples)`
- bounded `rho` optimization using `scipy.optimize.minimize_scalar`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dixon_coles_model_service.py -q`

Expected: PASS.

### Task 4: 推荐层消费统一模型分布

**Files:**
- Modify: `src/icewine_prediction/recommendation_service.py`
- Test: `tests/test_model_recommendation_service.py`

- [ ] **Step 1: Write failing test**

Add a test proving `build_model_recommendations_from_features` accepts `DixonColesGoalModel` and returns both asian handicap and total goals recommendations.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model_recommendation_service.py::test_model_recommendations_accept_dixon_coles_model -q`

Expected: FAIL because recommendation service does not consume Dixon-Coles through the unified model entrance.

- [ ] **Step 3: Write minimal implementation**

Update recommendation service to call `predict_goal_distribution_from_model`, then build `ScoreProbabilityGrid` from returned score probabilities.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_model_recommendation_service.py::test_model_recommendations_accept_dixon_coles_model -q`

Expected: PASS.

### Task 5: CLI 训练命令

**Files:**
- Modify: `src/icewine_prediction/cli.py`
- Test: `tests/test_models_cli.py`

- [ ] **Step 1: Write failing test**

Add a test for `icewine models train-dixon-coles`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models_cli.py::test_models_train_dixon_coles_outputs_parameters -q`

Expected: FAIL because the command is missing.

- [ ] **Step 3: Write minimal implementation**

Import `train_dixon_coles_goal_model`, train from `list_training_samples`, and output sample count, expected goals, `rho`, and result probabilities.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models_cli.py::test_models_train_dixon_coles_outputs_parameters -q`

Expected: PASS.

### Task 6: Verification

**Files:**
- All files touched above.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_goal_distribution_service.py tests/test_score_model_service.py tests/test_dixon_coles_model_service.py tests/test_model_recommendation_service.py tests/test_models_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
python -m pytest tests -q
```

Expected: PASS or report missing local dependencies if the current environment is not installed.

- [ ] **Step 3: Review diff**

Run:

```powershell
git diff -- src tests pyproject.toml docs
```

Expected: Diff only includes Dixon-Coles, unified score model interface, docs, and tests.

## Self-Review

- Spec coverage: 计划覆盖公共比分分布构造、统一模型入口、Dixon-Coles 模型、推荐层接入、CLI 命令和验证。
- Placeholder scan: 没有未决占位；每个任务都有目标文件、测试和命令。
- Type consistency: 统一输出类型为 `GoalDistributionPrediction`，推荐层继续使用现有 `ScoreProbabilityGrid` 计算盘口概率。
