# Filtered Match Automation Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在比赛列表中一键为当前完整筛选结果的所有可用开赛时间创建 T-9 自动任务，并安全跳过过期或已被活动任务覆盖的时间段。

**Architecture:** 后端复用 `select_match_list_sync_targets` 取得不受 200 行展示限制的完整比赛集合，再由 `paper_automation_service` 负责黑名单、按开赛时间分组、T-9 计算、宽窗口覆盖去重和单事务写入。前端提交当前筛选条件，使用独立纯函数格式化汇总并合并返回任务，通过小型操作组件呈现手动与一键入口。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、TypeScript、React、Vitest、Vite、lucide-react

---

## File Map

- Modify `src/icewine_prediction/paper_automation_service.py`: 定义批量结果类型、共享任务构造器及批量分组创建事务。
- Modify `tests/test_paper_automation_service.py`: 覆盖 T-9、同时间分组、黑名单、宽窗口去重、历史终态和事务回滚。
- Modify `src/icewine_prediction/web_api.py`: 新增筛选条件批量创建接口和响应构建。
- Modify `tests/test_web_console_api.py`: 覆盖筛选参数、成功/空结果响应及无效参数。
- Modify `web/src/types.ts`: 定义批量创建响应类型。
- Modify `web/src/apiClient.ts`: 增加批量请求并序列化多选赔率状态。
- Modify `web/src/apiClient.test.ts`: 验证请求路径、方法和完整筛选体。
- Create `web/src/paperAutomationBatch.ts`: 格式化批量结果并合并新任务。
- Create `web/src/paperAutomationBatch.test.ts`: 覆盖汇总和去重合并。
- Create `web/src/components/MatchAutomationActions.tsx`: 呈现手动创建与一键创建按钮。
- Create `web/src/components/MatchAutomationActions.test.tsx`: 验证按钮文案和忙碌禁用状态。
- Modify `web/src/pages/DashboardPage.tsx`: 接入批量调用、状态、消息及新操作组件。

## Global Constraints

- PowerShell 中固定使用 `C:\ProgramData\anaconda3\python.exe`，并设置 `PYTHONPATH=src`、`PYTHONIOENCODING=utf-8`。
- 手工编辑使用 `apply_patch`。
- 不修改 `paper_automation_tasks` 表结构，不改变现有手动创建接口的校验口径。
- 不改动用户当前未暂存的 `config/display_names.yaml`。
- 每次 Git 提交只暂存对应任务文件，提交信息使用中文。

### Task 1: 批量任务领域服务

**Files:**
- Modify: `src/icewine_prediction/paper_automation_service.py:44-170`
- Test: `tests/test_paper_automation_service.py:1-150`
- Test: `tests/test_paper_automation_service.py:1038-1180`

**Interfaces:**

```python
@dataclass(frozen=True)
class PaperAutomationBatchResult:
    matched_match_count: int
    excluded_match_count: int
    eligible_match_count: int
    time_slot_count: int
    skipped_existing_count: int
    skipped_expired_count: int
    tasks: tuple[PaperAutomationTask, ...]

    @property
    def created_count(self) -> int:
        return len(self.tasks)


```

- `create_filtered_paper_automation_tasks(session, *, matches, now, created_by="web", excluded_source_league_ids=None) -> PaperAutomationBatchResult`

- [ ] **Step 1: 导入批量服务并写分组、T-9、过期、宽窗口和黑名单失败测试**

在 `tests/test_paper_automation_service.py` 的导入列表加入 `create_filtered_paper_automation_tasks`，新增：

```python
def test_create_filtered_tasks_groups_slots_and_reports_all_skip_reasons():
    now = datetime(2026, 7, 27, 17, 0, tzinfo=BEIJING)
    expired = now + timedelta(minutes=9)
    covered = now + timedelta(hours=1)
    fresh = now + timedelta(hours=2)
    with _session() as session:
        matches = [
            _seed_match_for_league(
                session,
                kickoff=expired,
                source_match_id="expired",
                source_league_id="10",
                league_name="Expired League",
            ),
            _seed_match_for_league(
                session,
                kickoff=covered,
                source_match_id="covered",
                source_league_id="11",
                league_name="Covered League",
            ),
            _seed_match_for_league(
                session,
                kickoff=fresh,
                source_match_id="fresh-a",
                source_league_id="12",
                league_name="Fresh League A",
            ),
            _seed_match_for_league(
                session,
                kickoff=fresh,
                source_match_id="fresh-b",
                source_league_id="13",
                league_name="Fresh League B",
            ),
            _seed_match_for_league(
                session,
                kickoff=fresh,
                source_match_id="excluded",
                source_league_id="2",
                league_name="Excluded League",
            ),
        ]
        _seed_running_task(
            session,
            match_window_start=covered - timedelta(minutes=30),
            match_window_end=covered + timedelta(minutes=30),
            now=now,
        )

        result = create_filtered_paper_automation_tasks(
            session,
            matches=matches,
            now=now,
            excluded_source_league_ids={"2"},
        )

        assert result.matched_match_count == 5
        assert result.excluded_match_count == 1
        assert result.eligible_match_count == 4
        assert result.time_slot_count == 3
        assert result.created_count == 1
        assert result.skipped_existing_count == 1
        assert result.skipped_expired_count == 1
        assert paper_automation_service.as_beijing_datetime(
            result.tasks[0].trigger_at
        ) == fresh - timedelta(minutes=9)
        assert paper_automation_service.as_beijing_datetime(
            result.tasks[0].match_window_start
        ) == fresh
        assert paper_automation_service.as_beijing_datetime(
            result.tasks[0].match_window_end
        ) == fresh
```

- [ ] **Step 2: 写历史终态不阻止创建的失败测试**

```python
@pytest.mark.parametrize("status", ["success", "failed", "missed", "cancelled"])
def test_create_filtered_tasks_ignores_terminal_task_windows(status):
    now = datetime(2026, 7, 27, 17, 0, tzinfo=BEIJING)
    kickoff = now + timedelta(hours=1)
    with _session() as session:
        match = _seed_match(session, kickoff)
        session.add(
            PaperAutomationTask(
                created_at=now,
                updated_at=now,
                created_by="test",
                trigger_at=kickoff - timedelta(minutes=9),
                match_window_start=kickoff,
                match_window_end=kickoff,
                status=status,
                notification_status="pending",
            )
        )
        session.commit()

        result = create_filtered_paper_automation_tasks(
            session,
            matches=[match],
            now=now,
            excluded_source_league_ids=set(),
        )

        assert result.created_count == 1
        assert result.skipped_existing_count == 0
```

- [ ] **Step 3: 写提交异常整体回滚的失败测试**

```python
def test_create_filtered_tasks_rolls_back_all_new_tasks_when_commit_fails(monkeypatch):
    now = datetime(2026, 7, 27, 17, 0, tzinfo=BEIJING)
    with _session() as session:
        matches = [
            _seed_match_for_league(
                session,
                kickoff=now + timedelta(hours=index),
                source_match_id=f"rollback-{index}",
                source_league_id=str(100 + index),
                league_name=f"Rollback League {index}",
            )
            for index in (1, 2)
        ]
        real_commit = session.commit

        def fail_commit():
            raise RuntimeError("commit failed")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="commit failed"):
            create_filtered_paper_automation_tasks(
                session,
                matches=matches,
                now=now,
                excluded_source_league_ids=set(),
            )
        monkeypatch.setattr(session, "commit", real_commit)

        assert session.query(PaperAutomationTask).count() == 0
```

- [ ] **Step 4: 运行聚焦测试确认 RED**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest tests\test_paper_automation_service.py -q
```

Expected: collection 因 `create_filtered_paper_automation_tasks` 尚不存在而失败。

- [ ] **Step 5: 实现共享任务构造器和批量服务**

在 `paper_automation_service.py` 增加结果类型，并把手动创建中的 ORM 初始值提取为共享构造器：

```python
@dataclass(frozen=True)
class PaperAutomationBatchResult:
    matched_match_count: int
    excluded_match_count: int
    eligible_match_count: int
    time_slot_count: int
    skipped_existing_count: int
    skipped_expired_count: int
    tasks: tuple[PaperAutomationTask, ...]

    @property
    def created_count(self) -> int:
        return len(self.tasks)


def _new_paper_automation_task(
    *,
    trigger_at: datetime,
    match_window_start: datetime,
    match_window_end: datetime,
    now: datetime,
    created_by: str,
) -> PaperAutomationTask:
    return PaperAutomationTask(
        created_at=now,
        updated_at=now,
        created_by=created_by,
        trigger_at=trigger_at,
        match_window_start=match_window_start,
        match_window_end=match_window_end,
        status="pending",
        notification_status="pending",
    )
```

将 `create_paper_automation_task` 中直接构造 `PaperAutomationTask` 的代码替换为对 `_new_paper_automation_task` 的调用，保留其现有 `session.add()` 和 `session.commit()`。

新增批量实现：

```python
def create_filtered_paper_automation_tasks(
    session: Session,
    *,
    matches: list[Match],
    now: datetime,
    created_by: str = "web",
    excluded_source_league_ids: set[str] | None = None,
) -> PaperAutomationBatchResult:
    now = as_beijing_datetime(now)
    excluded_ids = _normalize_excluded_source_league_ids(excluded_source_league_ids)
    matched_matches = list(matches)
    eligible_matches = [
        match
        for match in matched_matches
        if match.league.source_league_id is None
        or str(match.league.source_league_id).strip() not in excluded_ids
    ]
    kickoff_times = sorted(
        {as_beijing_datetime(match.kickoff_time) for match in eligible_matches}
    )
    active_tasks = (
        session.query(PaperAutomationTask)
        .filter(PaperAutomationTask.status.in_(("pending", "running")))
        .all()
    )
    tasks: list[PaperAutomationTask] = []
    skipped_existing_count = 0
    skipped_expired_count = 0

    for kickoff_time in kickoff_times:
        trigger_at = kickoff_time - timedelta(minutes=9)
        if trigger_at <= now:
            skipped_expired_count += 1
            continue
        if any(
            as_beijing_datetime(task.match_window_start)
            <= kickoff_time
            <= as_beijing_datetime(task.match_window_end)
            for task in active_tasks
        ):
            skipped_existing_count += 1
            continue
        task = _new_paper_automation_task(
            trigger_at=trigger_at,
            match_window_start=kickoff_time,
            match_window_end=kickoff_time,
            now=now,
            created_by=created_by,
        )
        tasks.append(task)
        active_tasks.append(task)

    try:
        session.add_all(tasks)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return PaperAutomationBatchResult(
        matched_match_count=len(matched_matches),
        excluded_match_count=len(matched_matches) - len(eligible_matches),
        eligible_match_count=len(eligible_matches),
        time_slot_count=len(kickoff_times),
        skipped_existing_count=skipped_existing_count,
        skipped_expired_count=skipped_expired_count,
        tasks=tuple(tasks),
    )
```

- [ ] **Step 6: 运行服务测试确认 GREEN**

使用 Step 4 命令。Expected: `tests/test_paper_automation_service.py` 全部通过。

- [ ] **Step 7: 提交领域服务**

```powershell
git add src/icewine_prediction/paper_automation_service.py tests/test_paper_automation_service.py
git commit -m "增加筛选比赛批量自动任务服务"
```

### Task 2: 批量创建 Web API

**Files:**
- Modify: `src/icewine_prediction/web_api.py:50-95`
- Modify: `src/icewine_prediction/web_api.py:925-970`
- Modify: `tests/test_web_console_api.py:1-35`
- Modify: `tests/test_web_console_api.py:3291-3410`

- [ ] **Step 1: 写完整筛选请求及响应失败测试**

在 `tests/test_web_console_api.py` 导入 `PaperAutomationTask`，新增：

```python
def test_web_console_api_creates_automation_tasks_from_match_filters(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            start_paper_automation_scheduler=False,
            clock=lambda: datetime(2026, 5, 20, 20, 0, tzinfo=BEIJING),
        )
    )

    response = client.post(
        "/api/paper-automation/tasks/from-match-filters",
        json={
            "start_time": "2026-05-20T21:30:00+08:00",
            "end_time": "2026-05-20T22:30:00+08:00",
            "league_name": "英冠",
            "status_filter": "finished",
            "odds_filter": "all",
            "search": "Cardiff",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {key: payload[key] for key in (
        "matched_match_count",
        "excluded_match_count",
        "eligible_match_count",
        "time_slot_count",
        "created_count",
        "skipped_existing_count",
        "skipped_expired_count",
    )} == {
        "matched_match_count": 1,
        "excluded_match_count": 0,
        "eligible_match_count": 1,
        "time_slot_count": 1,
        "created_count": 1,
        "skipped_existing_count": 0,
        "skipped_expired_count": 0,
    }
    assert len(payload["tasks"]) == 1
    task = payload["tasks"][0]
    assert task["trigger_at"] == "2026-05-20T21:51:00+08:00"
    assert task["match_window_start"] == "2026-05-20T22:00:00+08:00"
    assert task["match_window_end"] == "2026-05-20T22:00:00+08:00"
    assert task["target_match_count"] == 1
```

- [ ] **Step 2: 写空结果和无效时间失败测试**

```python
def test_web_console_api_filtered_automation_returns_empty_summary(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            start_paper_automation_scheduler=False,
        )
    )

    response = client.post(
        "/api/paper-automation/tasks/from-match-filters",
        json={"start_time": "2026-07-27T00:00", "end_time": "2026-07-28T00:00"},
    )

    assert response.status_code == 200
    assert response.json()["matched_match_count"] == 0
    assert response.json()["created_count"] == 0
    assert response.json()["tasks"] == []


def test_web_console_api_filtered_automation_rejects_invalid_time(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            start_paper_automation_scheduler=False,
        )
    )

    response = client.post(
        "/api/paper-automation/tasks/from-match-filters",
        json={"start_time": "not-a-time", "end_time": "2026-07-28T00:00"},
    )

    assert response.status_code == 400
    assert "自动任务筛选参数错误" in response.json()["detail"]
```

- [ ] **Step 3: 运行 API 测试确认 RED**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest tests\test_web_console_api.py -q
```

Expected: 新接口当前返回 404。

- [ ] **Step 4: 导入服务并实现批量响应构建器**

在 `web_api.py` 的自动任务服务导入列表加入 `PaperAutomationBatchResult` 和 `create_filtered_paper_automation_tasks`，新增：

```python
def build_paper_automation_batch_payload(
    session: Session,
    result: PaperAutomationBatchResult,
) -> dict[str, Any]:
    return {
        "matched_match_count": result.matched_match_count,
        "excluded_match_count": result.excluded_match_count,
        "eligible_match_count": result.eligible_match_count,
        "time_slot_count": result.time_slot_count,
        "created_count": result.created_count,
        "skipped_existing_count": result.skipped_existing_count,
        "skipped_expired_count": result.skipped_expired_count,
        "tasks": [build_paper_automation_task_payload(session, task) for task in result.tasks],
    }
```

- [ ] **Step 5: 实现筛选批量创建接口**

把静态批量路由放在任务详情路由之前：

```python
    @app.post("/api/paper-automation/tasks/from-match-filters")
    def create_filtered_paper_automation_tasks_endpoint(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = clock()
        with session_factory() as session:
            try:
                matches = _select_sync_matches_from_payload(session, payload, now=now)
            except (TypeError, ValueError) as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"自动任务筛选参数错误: {error}",
                ) from error
            result = create_filtered_paper_automation_tasks(
                session,
                matches=matches,
                now=now,
            )
            return build_paper_automation_batch_payload(session, result)
```

- [ ] **Step 6: 运行 API 与比赛筛选回归测试确认 GREEN**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest tests\test_web_console_api.py tests\test_match_list_workspace_service.py -q
```

Expected: 两个测试文件全部通过，且完整目标选择仍不应用 200 行展示上限。

- [ ] **Step 7: 提交 Web API**

```powershell
git add src/icewine_prediction/web_api.py tests/test_web_console_api.py
git commit -m "提供筛选比赛批量自动任务接口"
```

### Task 3: 前端类型、API 与结果纯函数

**Files:**
- Modify: `web/src/types.ts:590-640`
- Modify: `web/src/apiClient.ts:1-40`
- Modify: `web/src/apiClient.ts:371-390`
- Test: `web/src/apiClient.test.ts:680-750`
- Create: `web/src/paperAutomationBatch.ts`
- Create: `web/src/paperAutomationBatch.test.ts`

- [ ] **Step 1: 写批量 API 请求失败测试**

在 `apiClient.test.ts` 导入 `createFilteredPaperAutomationTasks`，新增：

```typescript
it("creates filtered paper automation tasks with the full match filter payload", async () => {
  const fetchMock = vi.fn(async () =>
    Response.json({
      matched_match_count: 12,
      excluded_match_count: 1,
      eligible_match_count: 11,
      time_slot_count: 4,
      created_count: 0,
      skipped_existing_count: 3,
      skipped_expired_count: 1,
      tasks: []
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  await createFilteredPaperAutomationTasks({
    start_time: "2026-07-27T00:00",
    end_time: "2026-07-28T00:00",
    league_name: "Premier League",
    status_filter: "not_started",
    odds_filter: ["none", "partial"],
    search: "Arsenal"
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/paper-automation/tasks/from-match-filters",
    {
      body: JSON.stringify({
        start_time: "2026-07-27T00:00",
        end_time: "2026-07-28T00:00",
        league_name: "Premier League",
        status_filter: "not_started",
        odds_filter: "none,partial",
        search: "Arsenal"
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    }
  );
});
```

- [ ] **Step 2: 写汇总格式化和任务合并失败测试**

创建 `paperAutomationBatch.test.ts`：

```typescript
import { describe, expect, it } from "vitest";

import {
  formatFilteredAutomationResult,
  mergePaperAutomationTasks
} from "./paperAutomationBatch";
import type { PaperAutomationTask } from "./types";

function task(id: number): PaperAutomationTask {
  return {
    id,
    created_by: "web",
    created_at: "2026-07-27T17:00:00+08:00",
    updated_at: "2026-07-27T17:00:00+08:00",
    trigger_at: "2026-07-27T17:51:00+08:00",
    match_window_start: "2026-07-27T18:00:00+08:00",
    match_window_end: "2026-07-27T18:00:00+08:00",
    started_at: null,
    finished_at: null,
    missed_at: null,
    cancelled_at: null,
    status: "pending",
    notification_status: "pending",
    notification_error: null,
    error_message: null,
    target_match_count: 1,
    result_payload: null
  };
}

describe("filtered paper automation batch helpers", () => {
  it("formats created, skipped, and excluded counts", () => {
    expect(
      formatFilteredAutomationResult({
        matched_match_count: 12,
        excluded_match_count: 1,
        eligible_match_count: 11,
        time_slot_count: 4,
        created_count: 2,
        skipped_existing_count: 1,
        skipped_expired_count: 1,
        tasks: [task(2), task(3)]
      })
    ).toBe(
      "筛选 12 场比赛、4 个时间段：创建 2 个任务，已有任务跳过 1 个，已过 T-9 跳过 1 个，黑名单排除 1 场"
    );
  });

  it("prepends created tasks without duplicate ids", () => {
    expect(mergePaperAutomationTasks([task(1), task(2)], [task(2), task(3)]).map((row) => row.id))
      .toEqual([2, 3, 1]);
  });
});
```

- [ ] **Step 3: 运行前端聚焦测试确认 RED**

```powershell
Set-Location web
npm test -- src/apiClient.test.ts src/paperAutomationBatch.test.ts --reporter=dot
```

Expected: 导入的类型、API 和纯函数尚不存在，测试失败。

- [ ] **Step 4: 增加响应类型和 API 客户端**

在 `types.ts` 增加：

```typescript
export type CreateFilteredPaperAutomationTasksResult = {
  matched_match_count: number;
  excluded_match_count: number;
  eligible_match_count: number;
  time_slot_count: number;
  created_count: number;
  skipped_existing_count: number;
  skipped_expired_count: number;
  tasks: PaperAutomationTask[];
};
```

在 `apiClient.ts` 导入该类型和 `MatchListFilters`，增加：

```typescript
export async function createFilteredPaperAutomationTasks(
  filters: MatchListFilters
): Promise<CreateFilteredPaperAutomationTasksResult> {
  return await postJson<CreateFilteredPaperAutomationTasksResult>(
    "/api/paper-automation/tasks/from-match-filters",
    {
      ...filters,
      odds_filter: serializeOddsFilter(filters.odds_filter)
    }
  );
}
```

- [ ] **Step 5: 实现汇总和合并纯函数**

创建 `paperAutomationBatch.ts`：

```typescript
import type {
  CreateFilteredPaperAutomationTasksResult,
  PaperAutomationTask
} from "./types";

export function formatFilteredAutomationResult(
  result: CreateFilteredPaperAutomationTasksResult
): string {
  const parts = [
    `创建 ${result.created_count} 个任务`,
    `已有任务跳过 ${result.skipped_existing_count} 个`,
    `已过 T-9 跳过 ${result.skipped_expired_count} 个`
  ];
  if (result.excluded_match_count > 0) {
    parts.push(`黑名单排除 ${result.excluded_match_count} 场`);
  }
  return `筛选 ${result.matched_match_count} 场比赛、${result.time_slot_count} 个时间段：${parts.join("，")}`;
}

export function mergePaperAutomationTasks(
  current: PaperAutomationTask[],
  created: PaperAutomationTask[]
): PaperAutomationTask[] {
  const createdIds = new Set(created.map((task) => task.id));
  return [...created, ...current.filter((task) => !createdIds.has(task.id))];
}
```

- [ ] **Step 6: 运行前端聚焦测试确认 GREEN**

使用 Step 3 命令。Expected: 两个测试文件全部通过。

- [ ] **Step 7: 提交前端数据层**

```powershell
Set-Location ..
git add web/src/types.ts web/src/apiClient.ts web/src/apiClient.test.ts web/src/paperAutomationBatch.ts web/src/paperAutomationBatch.test.ts
git commit -m "增加批量自动任务前端数据层"
```

### Task 4: 比赛列表一键创建交互

**Files:**
- Create: `web/src/components/MatchAutomationActions.tsx`
- Create: `web/src/components/MatchAutomationActions.test.tsx`
- Modify: `web/src/pages/DashboardPage.tsx:1-155`
- Modify: `web/src/pages/DashboardPage.tsx:560-610`
- Modify: `web/src/pages/DashboardPage.tsx:1287-1475`
- Modify: `web/src/pages/DashboardPage.tsx:2157-2180`

- [ ] **Step 1: 写操作组件的失败渲染测试**

创建 `MatchAutomationActions.test.tsx`：

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MatchAutomationActions } from "./MatchAutomationActions";

describe("MatchAutomationActions", () => {
  it("renders manual and filtered task actions", () => {
    const html = renderToStaticMarkup(
      <MatchAutomationActions
        isBusy={false}
        onCreateFiltered={vi.fn()}
        onCreateManual={vi.fn()}
      />
    );

    expect(html).toContain("创建自动任务");
    expect(html).toContain("一键创建筛选任务");
    expect(html).not.toContain("disabled");
  });

  it("disables both actions while a match-list operation is running", () => {
    const html = renderToStaticMarkup(
      <MatchAutomationActions
        isBusy
        onCreateFiltered={vi.fn()}
        onCreateManual={vi.fn()}
      />
    );

    expect((html.match(/disabled/g) ?? []).length).toBe(2);
  });
});
```

- [ ] **Step 2: 运行组件测试确认 RED**

```powershell
Set-Location web
npm test -- src/components/MatchAutomationActions.test.tsx --reporter=dot
```

Expected: 组件文件尚不存在，测试失败。

- [ ] **Step 3: 实现操作组件**

创建 `MatchAutomationActions.tsx`：

```tsx
import { Clock, ListPlus } from "lucide-react";

export function MatchAutomationActions({
  isBusy,
  onCreateFiltered,
  onCreateManual
}: {
  isBusy: boolean;
  onCreateFiltered: () => void;
  onCreateManual: () => void;
}) {
  return (
    <div className="sync-action">
      <button disabled={isBusy} onClick={onCreateManual} type="button">
        <Clock size={16} />
        创建自动任务
      </button>
      <button disabled={isBusy} onClick={onCreateFiltered} type="button">
        <ListPlus size={16} />
        一键创建筛选任务
      </button>
    </div>
  );
}
```

- [ ] **Step 4: 接入 Dashboard 数据流**

在 `DashboardPage.tsx`：

1. 从 `apiClient` 导入 `createFilteredPaperAutomationTasks`。
2. 导入 `MatchAutomationActions`。
3. 从 `paperAutomationBatch` 导入 `formatFilteredAutomationResult`、`mergePaperAutomationTasks`。
4. 给 `FilteredMatchListView` 增加 `onCreateFilteredAutomationTasks: () => void` 属性。
5. 用 `MatchAutomationActions` 替换当前只包含手动创建按钮的 `sync-action`。

顶层传入处理器：

```tsx
            onCreateFilteredAutomationTasks={() => {
              setMatchListAction("create-filtered-automation-tasks");
              setMatchListError(null);
              setMatchListMessage(null);
              createFilteredPaperAutomationTasks(matchListFilters)
                .then((result) => {
                  const message = formatFilteredAutomationResult(result);
                  setPaperAutomationTasks((current) =>
                    mergePaperAutomationTasks(current, result.tasks)
                  );
                  setMatchListMessage(message);
                  setAutomationTaskMessage(message);
                })
                .catch((error) =>
                  setMatchListError(formatActionError("一键创建自动任务失败", error))
                )
                .finally(() => setMatchListAction(null));
            }}
```

视图内替换为：

```tsx
        <MatchAutomationActions
          isBusy={isBusy}
          onCreateFiltered={onCreateFilteredAutomationTasks}
          onCreateManual={onCreateAutomationTask}
        />
```

在 `formatMatchListAction` 增加：

```typescript
  if (action === "create-filtered-automation-tasks") {
    return "一键创建筛选自动任务";
  }
```

- [ ] **Step 5: 运行组件及纯函数测试确认 GREEN**

```powershell
npm test -- src/components/MatchAutomationActions.test.tsx src/paperAutomationBatch.test.ts src/apiClient.test.ts --reporter=dot
```

Expected: 三个测试文件全部通过。

- [ ] **Step 6: 运行 TypeScript 生产构建**

```powershell
npm run build
```

Expected: `tsc` 与 Vite build 均成功，无类型错误。

- [ ] **Step 7: 提交比赛列表交互**

```powershell
Set-Location ..
git add web/src/components/MatchAutomationActions.tsx web/src/components/MatchAutomationActions.test.tsx web/src/pages/DashboardPage.tsx
git commit -m "增加筛选比赛一键自动任务按钮"
```

### Task 5: 集成回归与本地运行验证

**Files:**
- Verify only; no product files should change.

- [ ] **Step 1: 运行自动任务与比赛筛选后端回归**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest tests\test_paper_automation_service.py tests\test_paper_automation_scheduler.py tests\test_match_list_workspace_service.py tests\test_web_console_api.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行完整前端测试和构建**

```powershell
Set-Location web
npm test -- --reporter=dot
npm run build
Set-Location ..
```

Expected: Vitest 全部通过，TypeScript/Vite 构建成功。

- [ ] **Step 3: 检查差异和提交范围**

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: `git diff --check` 无输出；仅保留用户原有 `config/display_names.yaml` 修改和预期生成物，不出现未提交的产品代码。

- [ ] **Step 4: 启动 Web 控制台供验收**

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 status
```

Expected: 后端运行于 `http://127.0.0.1:8000`，前端运行于 `http://127.0.0.1:5173`。只验证页面加载、两个自动任务按钮同时存在和筛选按钮可点击；不要在真实本地数据库上实际提交批量创建，除非用户明确要求。
