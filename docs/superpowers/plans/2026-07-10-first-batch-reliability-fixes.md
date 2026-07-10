# First Batch Reliability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复自动任务遗留阻塞、前端写操作假成功和推荐队列遗留错误，并澄清校准 edge 的代码语义。

**Architecture:** 自动任务继续使用现有 SQLite/SQLAlchemy 状态机，通过保守超时回收和带状态条件的更新完成领取，不修改数据库结构。前端复用现有 `postJson` 错误传播；推荐队列仅清理不可达辅助函数并保留活跃的标准时点路径。

**Tech Stack:** Python 3.12、SQLAlchemy 2、pytest、TypeScript、Vitest、React/Vite。

## Global Constraints

- 直接在当前主工作区实施，用户已明确同意。
- Python 命令固定使用 `C:\Python312\python.exe`，并设置 `PYTHONPATH=src`、`PYTHONIOENCODING=utf-8`。
- 不修改推荐策略、模型输出、数据库结构和只读接口 mock 回退。
- 手工代码编辑使用 `apply_patch`。
- Git 提交信息使用中文，且每个提交只包含对应任务文件。

---

### Task 1: 自动任务遗留恢复和原子领取

**Files:**
- Modify: `src/icewine_prediction/paper_automation_service.py:216`
- Modify: `src/icewine_prediction/paper_automation_scheduler.py:18`
- Modify: `src/icewine_prediction/web_api.py:215`
- Test: `tests/test_paper_automation_service.py:1069`
- Test: `tests/test_paper_automation_scheduler.py:93`
- Test: `tests/test_web_console_api.py:60`

**Interfaces:**
- `claim_due_paper_automation_task(session, *, now, grace_minutes, running_timeout_minutes=360) -> PaperAutomationTask | None`
- `PaperAutomationScheduler.running_timeout_minutes: int = 360`
- 环境变量 `PAPER_AUTOMATION_RUNNING_TIMEOUT_MINUTES`，非法值回退为 `360`。

- [ ] **Step 1: 写遗留任务恢复失败测试**

```python
def test_claim_due_task_fails_stale_running_task_and_claims_pending():
    claimed = claim_due_paper_automation_task(
        session,
        now=now,
        grace_minutes=20,
        running_timeout_minutes=360,
    )
    assert stale.status == "failed"
    assert stale.finished_at == now
    assert claimed.id == pending.id
```

- [ ] **Step 2: 写条件领取冲突失败测试**

```python
def test_claim_pending_task_does_not_overwrite_competing_claim():
    competing_session.query(PaperAutomationTask).filter_by(id=task.id).update({"status": "running"})
    competing_session.commit()
    assert _claim_pending_task(session, task_id=task.id, now=now) is False
```

- [ ] **Step 3: 写调度器参数和 Web 环境变量失败测试**

```python
assert schedulers[0].kwargs["running_timeout_minutes"] == 360
```

并验证 `poll_paper_automation_once` 将显式 `running_timeout_minutes` 传给 service。

- [ ] **Step 4: 运行聚焦测试并确认 RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\Python312\python.exe' -m pytest tests\test_paper_automation_service.py tests\test_paper_automation_scheduler.py tests\test_web_console_api.py -q
```

Expected: 新测试因缺少 `running_timeout_minutes`、`_claim_pending_task` 或恢复行为而失败。

- [ ] **Step 5: 实现最小状态机修改**

```python
DEFAULT_RUNNING_TIMEOUT_MINUTES = 360

def _claim_pending_task(session: Session, *, task_id: int, now: datetime) -> bool:
    updated = (
        session.query(PaperAutomationTask)
        .filter(PaperAutomationTask.id == task_id)
        .filter(PaperAutomationTask.status == "pending")
        .update(
            {
                PaperAutomationTask.status: "running",
                PaperAutomationTask.started_at: now,
                PaperAutomationTask.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    session.commit()
    return updated == 1
```

`claim_due_paper_automation_task` 在 `running.started_at <= now - timedelta(minutes=running_timeout_minutes)` 时将旧任务标为 `failed`，否则返回 `None`；条件领取失败时清理 session 状态并重新循环。

- [ ] **Step 6: 运行聚焦测试并确认 GREEN**

使用 Step 4 命令，Expected: PASS。

- [ ] **Step 7: 提交自动任务修复**

```powershell
git add src/icewine_prediction/paper_automation_service.py src/icewine_prediction/paper_automation_scheduler.py src/icewine_prediction/web_api.py tests/test_paper_automation_service.py tests/test_paper_automation_scheduler.py tests/test_web_console_api.py
git commit -m "修复自动任务遗留阻塞和重复领取"
```

### Task 2: 前端写操作传播失败

**Files:**
- Modify: `web/src/apiClient.ts:158`
- Test: `web/src/apiClient.test.ts`

**Interfaces:**
- `markTeamDisplayNameWorkspaceDone()` 和 `saveTeamDisplayNames()` 保持现有返回类型；失败时 Promise reject。

- [ ] **Step 1: 写两个失败测试**

```typescript
it("throws when marking a display workspace done fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("mark failed", { status: 500 })));
  await expect(markTeamDisplayNameWorkspaceDone(49, 2026)).rejects.toThrow("mark failed");
});

it("throws when saving team display names fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("save failed", { status: 500 })));
  await expect(saveTeamDisplayNames({ Arsenal: "阿森纳" })).rejects.toThrow("save failed");
});
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `npm test -- src/apiClient.test.ts --reporter=dot`

Expected: 两个 Promise 当前 resolve，断言失败。

- [ ] **Step 3: 删除写操作 catch 回退**

```typescript
return await postJson("/api/display/team-name-workspace/done", { league_id: leagueId, season });
return await postJson("/api/display/team-names", { teams });
```

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `npm test -- src/apiClient.test.ts --reporter=dot`

Expected: PASS。

- [ ] **Step 5: 提交前端修复**

```powershell
git add web/src/apiClient.ts web/src/apiClient.test.ts
git commit -m "修复球队中文名写入失败假成功"
```

### Task 3: 清理推荐队列遗留辅助函数

**Files:**
- Modify: `src/icewine_prediction/paper_recommendation_queue_service.py:1005`
- Test: `tests/test_paper_recommendation_queue_service.py`

**Interfaces:**
- 删除 `_latest_historical_snapshots_for_match` 和 `_select_latest_pre_kickoff_pair`。
- 保留 `_historical_snapshots_for_execution_target` 和 `_select_execution_pair`。

- [ ] **Step 1: 写结构性失败测试**

```python
def test_paper_queue_does_not_keep_legacy_latest_historical_snapshot_helper():
    assert not hasattr(queue_service, "_latest_historical_snapshots_for_match")
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\Python312\python.exe' -m pytest tests\test_paper_recommendation_queue_service.py -q
```

Expected: helper 当前仍存在，断言失败。

- [ ] **Step 3: 删除两个不可达辅助函数**

删除完整定义，不修改周边活跃标准时点逻辑。

- [ ] **Step 4: 运行推荐队列测试并确认 GREEN**

使用 Step 2 命令，Expected: PASS。

- [ ] **Step 5: 提交死代码清理**

```powershell
git add src/icewine_prediction/paper_recommendation_queue_service.py tests/test_paper_recommendation_queue_service.py
git commit -m "清理推荐队列失效历史快照辅助函数"
```

### Task 4: 补充校准 edge 语义注释

**Files:**
- Modify: `src/icewine_prediction/paper_recommendation_queue_service.py:2146`

**Interfaces:** 不改变任何接口或行为。

- [ ] **Step 1: 增加最小注释**

```python
# Keep this edge on the raw model's selected side; calibrated_side separately records
# whether the calibrated model selected the same side.
calibrated_edge = _quantize(calibrated_edges[side_index])
```

- [ ] **Step 2: 运行推荐队列测试**

使用 Task 3 Step 2 命令，Expected: PASS。

- [ ] **Step 3: 提交注释**

```powershell
git add src/icewine_prediction/paper_recommendation_queue_service.py
git commit -m "说明校准模型边际字段语义"
```

### Task 5: 完整回归和差异审查

**Files:**
- Verify only.

- [ ] **Step 1: 运行完整后端测试**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\Python312\python.exe' -m pytest -q
```

Expected: 现有 787 项加新增测试全部通过。

- [ ] **Step 2: 运行完整前端测试和构建**

```powershell
Set-Location web
npm test -- --reporter=dot
npm run build
```

Expected: 现有 88 项加新增测试全部通过，构建退出码为 0。

- [ ] **Step 3: 检查差异和工作区**

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: 无空白错误，只保留计划文档的预期状态或已提交改动。

