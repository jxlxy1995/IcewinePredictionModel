# Dixon-Coles 攻防强度模型实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增可训练球队进攻、防守和主场优势的 Dixon-Coles 攻防强度模型。

**Architecture:** 在现有 `dixon_coles_model_service.py` 中新增攻防强度模型，复用已有 Dixon-Coles 低比分修正和比分分布构造。统一模型入口通过 `predict_match_goal_distribution(home, away)` 适配需要主客队上下文的模型，CLI 增加独立训练命令。

**Tech Stack:** Python 3.11+、Decimal、scipy、pytest、Typer、Asia/Shanghai 时间。

---

### Task 1: 模型训练与预测

**Files:**
- Modify: `src/icewine_prediction/dixon_coles_model_service.py`
- Test: `tests/test_dixon_coles_attack_defense_model_service.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:

- The model learns stronger expected goals for a historically strong home team against a weak away team.
- Unknown teams fall back to neutral parameters and still return normalized probabilities.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_dixon_coles_attack_defense_model_service.py -q
```

Expected: FAIL because `train_dixon_coles_attack_defense_model` is not defined.

- [ ] **Step 3: Write minimal implementation**

Add:

- `DixonColesAttackDefenseModel`
- `DixonColesTeamParameters`
- `train_dixon_coles_attack_defense_model(samples)`

Use `scipy.optimize.minimize` with bounded parameters and lightweight L2 regularization.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_dixon_coles_attack_defense_model_service.py -q
```

Expected: PASS.

### Task 2: 统一模型入口适配

**Files:**
- Modify: `src/icewine_prediction/score_model_service.py`
- Test: `tests/test_score_model_service.py`

- [ ] **Step 1: Write failing test**

Add a test proving `predict_goal_distribution_from_model` can consume `DixonColesAttackDefenseModel` when `ScoreModelContext` includes home and away team names.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_score_model_service.py::test_predict_goal_distribution_from_attack_defense_dixon_coles_model -q
```

Expected: FAIL because the unified entrance does not call `predict_match_goal_distribution`.

- [ ] **Step 3: Write minimal implementation**

In `score_model_service.py`, if a model has `predict_match_goal_distribution`, require home and away team names and call that method.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_score_model_service.py::test_predict_goal_distribution_from_attack_defense_dixon_coles_model -q
```

Expected: PASS.

### Task 3: CLI 训练命令

**Files:**
- Modify: `src/icewine_prediction/cli.py`
- Test: `tests/test_models_cli.py`

- [ ] **Step 1: Write failing test**

Add a test for:

```powershell
icewine models train-dixon-coles-attack-defense --limit 10
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_models_cli.py::test_models_train_dixon_coles_attack_defense_outputs_parameters -q
```

Expected: FAIL because the command is missing.

- [ ] **Step 3: Write minimal implementation**

Import `train_dixon_coles_attack_defense_model`, add formatter, and register the CLI command.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_models_cli.py::test_models_train_dixon_coles_attack_defense_outputs_parameters -q
```

Expected: PASS.

### Task 4: Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_dixon_coles_attack_defense_model_service.py tests/test_score_model_service.py tests/test_models_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run:

```powershell
python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 3: Run lint for touched files**

Run:

```powershell
python -m ruff check src tests/test_dixon_coles_attack_defense_model_service.py tests/test_score_model_service.py tests/test_models_cli.py
```

Expected: PASS for touched files.

## Self-Review

- Spec coverage: 覆盖攻防强度训练、未知球队回退、统一入口适配、CLI 命令和验证。
- Placeholder scan: 没有未决占位；每个任务都有文件、命令和期望结果。
- Type consistency: 模型通过 `predict_match_goal_distribution(home_team_name, away_team_name)` 输出 `GoalDistributionPrediction`，与统一入口保持一致。
