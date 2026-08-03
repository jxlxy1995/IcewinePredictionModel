# 推荐快照回顾 All 来源模式实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在推荐快照回顾页增加 All 来源选择，通过后端确定性去重提供可信的跨来源合并统计、来源分布和去重数量。

**Architecture:** Web API 将精确值 `snapshot_source=all` 映射为服务层的无来源过滤回顾；服务层按 `group_key` 和已确认的来源优先级选择唯一快照，然后以入选集合重算全部统计和样本。前端集中维护来源选项，扩展稳定的 workspace 类型，并复用现有指标卡和分组表展示去重数量、来源分布与信号数量。

**Tech Stack:** Python 3.12、SQLAlchemy、FastAPI、pytest、React 18、TypeScript、Vitest、Vite。

---

## 文件结构

- 修改 `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`
  - All 模式选择规则、去重元数据和来源分组。
- 修改 `tests/test_paper_recommendation_group_snapshot_service.py`
  - 服务层来源优先级、时间 tie-break 和具体来源兼容测试。
- 修改 `src/icewine_prediction/web_api.py`
  - `all` 查询值映射及新增 payload 字段。
- 修改 `tests/test_web_console_api.py`
  - API All 去重、来源分布和默认来源回归测试。
- 修改 `web/src/paperSnapshotReviewWorkspace.ts`
  - 集中来源选项及 All 模式去重指标卡。
- 修改 `web/src/paperSnapshotReviewWorkspace.test.ts`
  - 来源选项、默认值和指标卡测试。
- 修改 `web/src/apiClient.test.ts`
  - All 查询参数测试。
- 修改 `web/src/types.ts`
  - deduplication 与 by_snapshot_source 类型。
- 修改 `web/src/mockData.ts`
  - mock workspace 新字段。
- 修改 `web/src/pages/DashboardPage.tsx`
  - 下拉框、按来源、按信号数和通用副标题。

## Task 1：服务层 All 去重与来源统计

**Files:**
- Modify: `tests/test_paper_recommendation_group_snapshot_service.py`
- Modify: `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`

- [ ] **Step 1：写来源优先级失败测试**

在测试文件的 import 中加入 `build_snapshot_review_workspace`，新增测试。使用同一
record 创建四个相同 group key、不同来源的快照，并给 automation 设置可识别的
手数：

```python
def test_build_snapshot_review_workspace_all_sources_prefers_real_automation_snapshot(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    snapshots = []
    for source, stake in [
        ("historical_backfill", "0.50"),
        ("future_source", "0.75"),
        ("manual_record", "1.00"),
        ("automation", "1.50"),
    ]:
        snapshot = _snapshot(match, record)
        snapshot.snapshot_source = source
        snapshot.suggested_stake_units = Decimal(stake)
        snapshot.is_backfilled = source == "historical_backfill"
        snapshots.append(snapshot)
    session.add_all(snapshots)
    session.commit()

    workspace = build_snapshot_review_workspace(session, snapshot_source=None)

    assert workspace.summary.group_count == 1
    assert workspace.snapshots[0].snapshot_source == "automation"
    assert workspace.snapshots[0].suggested_stake_units == Decimal("1.50")
    assert workspace.deduplication.applied is True
    assert workspace.deduplication.input_group_count == 4
    assert workspace.deduplication.selected_group_count == 1
    assert workspace.deduplication.excluded_group_count == 3
    assert list(workspace.by_snapshot_source) == ["automation"]
```

- [ ] **Step 2：运行测试确认 RED**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py::test_build_snapshot_review_workspace_all_sources_prefers_real_automation_snapshot -q
```

Expected: FAIL，因为 workspace 还没有去重，且没有 `deduplication` 和
`by_snapshot_source`。

- [ ] **Step 3：实现最小服务结构和去重选择**

在服务文件增加：

```python
SNAPSHOT_REVIEW_SOURCE_PRIORITY = {
    "automation": 0,
    "manual_record": 1,
    "historical_backfill": 3,
}


@dataclass(frozen=True)
class SnapshotReviewDeduplication:
    applied: bool
    input_group_count: int
    selected_group_count: int
    excluded_group_count: int
```

给 `SnapshotReviewWorkspace` 增加：

```python
    by_snapshot_source: dict[str, SnapshotReportGroup]
    deduplication: SnapshotReviewDeduplication
```

将 `build_snapshot_review_workspace` 的参数改为：

```python
    snapshot_source: str | None = HISTORICAL_BACKFILL_SOURCE,
```

在构造 workspace 前选择快照：

```python
    input_snapshots = report.snapshots
    snapshots = (
        _deduplicate_snapshot_review_groups(input_snapshots)
        if snapshot_source is None
        else input_snapshots
    )
    deduplication = SnapshotReviewDeduplication(
        applied=snapshot_source is None,
        input_group_count=len(input_snapshots),
        selected_group_count=len(snapshots),
        excluded_group_count=len(input_snapshots) - len(snapshots),
    )
```

所有 `_group_snapshot_report(...)`、settled/sample 计算和 summary 改用
`snapshots`，summary 用 `_summarize_snapshots(snapshots)`。来源分组使用：

```python
        by_snapshot_source=_group_snapshot_report(
            snapshots,
            lambda snapshot: snapshot.snapshot_source,
        ),
        deduplication=deduplication,
```

新增私有选择函数：

```python
def _deduplicate_snapshot_review_groups(
    snapshots: list[PaperRecommendationGroupSnapshot],
) -> list[PaperRecommendationGroupSnapshot]:
    selected: dict[str, PaperRecommendationGroupSnapshot] = {}
    for snapshot in snapshots:
        current = selected.get(snapshot.group_key)
        if current is None or _snapshot_review_selection_key(snapshot) < _snapshot_review_selection_key(current):
            selected[snapshot.group_key] = snapshot
    return sorted(
        selected.values(),
        key=lambda snapshot: (snapshot.created_at, snapshot.id or 0),
    )


def _snapshot_review_selection_key(
    snapshot: PaperRecommendationGroupSnapshot,
) -> tuple[int, float, int]:
    source_priority = SNAPSHOT_REVIEW_SOURCE_PRIORITY.get(
        snapshot.snapshot_source,
        2,
    )
    created_timestamp = snapshot.created_at.timestamp() if snapshot.created_at else 0.0
    return source_priority, -created_timestamp, -(snapshot.id or 0)
```

- [ ] **Step 4：运行来源优先级测试确认 GREEN**

运行 Step 2 的命令。Expected: PASS。

- [ ] **Step 5：写来源回退、同来源最新快照和具体来源兼容失败测试**

先增加来源回退测试，使用两个不同比赛/group key：第一组只有 manual、未来来源
和 historical，第二组只有未来来源和 historical。断言第一组选择 manual，第二组
选择未来来源：

```python
def test_build_snapshot_review_workspace_all_sources_uses_source_fallback_order(session):
    first_match = _seed_match(session)
    second_match = _seed_match(
        session,
        source_match_id="fixture-2",
        kickoff_time=datetime(2026, 6, 23, 19, 0, tzinfo=BEIJING),
    )
    first_record = _paper_record(session, first_match)
    second_record = _paper_record(session, second_match)
    snapshots = []
    for match, record, sources in [
        (first_match, first_record, ["historical_backfill", "future_source", "manual_record"]),
        (second_match, second_record, ["historical_backfill", "future_source"]),
    ]:
        for source in sources:
            snapshot = _snapshot(match, record)
            snapshot.snapshot_source = source
            snapshot.is_backfilled = source == "historical_backfill"
            snapshots.append(snapshot)
    session.add_all(snapshots)
    session.commit()

    workspace = build_snapshot_review_workspace(session, snapshot_source=None)

    assert {
        snapshot.group_key: snapshot.snapshot_source
        for snapshot in workspace.snapshots
    } == {
        f"{first_match.id}:asian_handicap:away_cover": "manual_record",
        f"{second_match.id}:asian_handicap:away_cover": "future_source",
    }
```

再增加同来源时间和 ID tie-break 测试：

```python
def test_build_snapshot_review_workspace_all_sources_prefers_latest_snapshot_within_source(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    older = _snapshot(match, record)
    older.snapshot_source = "manual_record"
    older.created_at = datetime(2026, 6, 22, 12, 0, tzinfo=BEIJING)
    older.suggested_stake_units = Decimal("0.75")
    newer = _snapshot(match, record)
    newer.snapshot_source = "manual_record"
    newer.created_at = datetime(2026, 6, 22, 13, 0, tzinfo=BEIJING)
    newer.suggested_stake_units = Decimal("1.25")
    newer.signal_record_ids_json = json.dumps([record.id, record.id + 1000])
    session.add_all([older, newer])
    session.commit()

    workspace = build_snapshot_review_workspace(session, snapshot_source=None)

    assert workspace.summary.group_count == 1
    assert workspace.snapshots[0].id == newer.id
    assert workspace.snapshots[0].suggested_stake_units == Decimal("1.25")


def test_build_snapshot_review_workspace_all_sources_uses_larger_id_when_created_at_ties(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    first = _snapshot(match, record)
    first.snapshot_source = "manual_record"
    first.created_at = datetime(2026, 6, 22, 13, 0, tzinfo=BEIJING)
    first.suggested_stake_units = Decimal("0.75")
    second = _snapshot(match, record)
    second.snapshot_source = "manual_record"
    second.created_at = first.created_at
    second.suggested_stake_units = Decimal("1.25")
    second.signal_record_ids_json = json.dumps([record.id, record.id + 1000])
    session.add_all([first, second])
    session.commit()

    workspace = build_snapshot_review_workspace(session, snapshot_source=None)

    assert second.id > first.id
    assert workspace.snapshots[0].id == second.id
    assert workspace.snapshots[0].suggested_stake_units == Decimal("1.25")


def test_build_snapshot_review_workspace_specific_source_keeps_existing_row_semantics(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    first = _snapshot(match, record)
    second = _snapshot(match, record)
    second.signal_record_ids_json = json.dumps([record.id, record.id + 1000])
    session.add_all([first, second])
    session.commit()

    workspace = build_snapshot_review_workspace(session, snapshot_source="manual_record")

    assert workspace.summary.group_count == 2
    assert workspace.deduplication.applied is False
    assert workspace.deduplication.input_group_count == 2
    assert workspace.deduplication.selected_group_count == 2
    assert workspace.deduplication.excluded_group_count == 0
```

- [ ] **Step 6：运行两个测试确认行为**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py -q
```

Expected: 新增测试和既有 snapshot service 测试全部 PASS。

- [ ] **Step 7：提交服务层改动**

```powershell
git add src/icewine_prediction/paper_recommendation_group_snapshot_service.py tests/test_paper_recommendation_group_snapshot_service.py
git commit -m "支持推荐快照全部来源去重"
```

## Task 2：Web API All 契约

**Files:**
- Modify: `tests/test_web_console_api.py`
- Modify: `src/icewine_prediction/web_api.py`

- [ ] **Step 1：写 API All 失败测试**

在现有 `test_web_console_api_paper_snapshot_review_returns_diagnostics` 附近新增测试。
同一代表记录创建 historical 与 automation 两个相同 group key 快照：

```python
def test_web_console_api_paper_snapshot_review_all_deduplicates_and_reports_sources(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        match = _seed_web_snapshot_match(session)
        record = _paper_snapshot_record(
            match,
            strategy_key="asian_away_cover_hgb_edge_v1",
            strategy_display_name="Asian away edge",
            edge=Decimal("0.2100"),
        )
        session.add(record)
        session.flush()
        historical = _paper_snapshot(
            record,
            group_key=f"{match.id}:asian_handicap:away_cover",
            confidence_score=55,
            suggested_stake_units=Decimal("0.50"),
            stake_cap_reason="historical",
            signal_families='["asian_away_hgb"]',
        )
        automation = _paper_snapshot(
            record,
            group_key=f"{match.id}:asian_handicap:away_cover",
            confidence_score=85,
            suggested_stake_units=Decimal("1.50"),
            stake_cap_reason="automation",
            signal_families='["asian_away_hgb"]',
        )
        automation.snapshot_source = "automation"
        automation.is_backfilled = False
        session.add_all([historical, automation])
        session.commit()

    client = TestClient(create_web_app(
        session_factory=session_factory,
        log_dir=tmp_path,
        start_paper_automation_scheduler=False,
    ))
    response = client.get("/api/paper-snapshot-review?snapshot_source=all")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["snapshot_source"] == "all"
    assert payload["summary"]["group_count"] == 1
    assert payload["summary"]["suggested_stake_units"] == "1.50"
    assert payload["deduplication"] == {
        "applied": True,
        "input_group_count": 2,
        "selected_group_count": 1,
        "excluded_group_count": 1,
    }
    assert [group["group_name"] for group in payload["groups"]["by_snapshot_source"]] == ["automation"]
```

- [ ] **Step 2：运行 API 测试确认 RED**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_paper_snapshot_review_all_deduplicates_and_reports_sources -q
```

Expected: FAIL，因为 `all` 仍被当作普通来源过滤。

- [ ] **Step 3：实现 endpoint 映射和 payload**

在 endpoint 内保留原始查询值用于 cache key 和 filters，并将服务参数映射为：

```python
                    build_snapshot_review_workspace(
                        session,
                        from_date=_parse_optional_datetime(from_date),
                        to_date=_parse_optional_datetime(to_date),
                        snapshot_source=None if snapshot_source == "all" else snapshot_source,
                        snapshot_version=snapshot_version,
                    ),
```

在 `build_paper_snapshot_review_payload` 返回中增加：

```python
        "deduplication": {
            "applied": workspace.deduplication.applied,
            "input_group_count": workspace.deduplication.input_group_count,
            "selected_group_count": workspace.deduplication.selected_group_count,
            "excluded_group_count": workspace.deduplication.excluded_group_count,
        },
```

并在 `groups` 中增加：

```python
            "by_snapshot_source": build_paper_snapshot_review_group_list(
                workspace.by_snapshot_source,
                sort_by="group_name",
            ),
```

- [ ] **Step 4：更新默认来源 API 断言**

给现有 diagnostics 测试补充：

```python
    assert payload["deduplication"] == {
        "applied": False,
        "input_group_count": 2,
        "selected_group_count": 2,
        "excluded_group_count": 0,
    }
    assert payload["groups"]["by_snapshot_source"][0]["group_name"] == "historical_backfill"
```

- [ ] **Step 5：运行 Web API 聚焦测试确认 GREEN**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -k "paper_snapshot_review" -q
```

Expected: All 和默认来源相关测试全部 PASS。

- [ ] **Step 6：提交 API 改动**

```powershell
git add src/icewine_prediction/web_api.py tests/test_web_console_api.py
git commit -m "扩展推荐快照全部来源接口"
```

## Task 3：前端来源选项、类型和指标卡

**Files:**
- Modify: `web/src/paperSnapshotReviewWorkspace.test.ts`
- Modify: `web/src/paperSnapshotReviewWorkspace.ts`
- Modify: `web/src/apiClient.test.ts`
- Modify: `web/src/types.ts`
- Modify: `web/src/mockData.ts`

- [ ] **Step 1：写来源选项和 All 卡片失败测试**

在 helper 测试 import 中加入 `paperSnapshotReviewSourceOptions`，给 fixture 增加
deduplication 和 by_snapshot_source，然后新增：

```typescript
it("offers all snapshot sources without changing the default source", () => {
  expect(paperSnapshotReviewSourceOptions).toEqual([
    { label: "全部来源（All）", value: "all" },
    { label: "historical_backfill", value: "historical_backfill" },
    { label: "manual_record", value: "manual_record" },
    { label: "automation", value: "automation" }
  ]);
  expect(defaultPaperSnapshotReviewFilters(new Date(2026, 5, 24, 15, 0)).snapshot_source)
    .toBe("historical_backfill");
});

it("adds the deduplicated count card only for all sources", () => {
  const allWorkspace = {
    ...workspace,
    filters: { ...workspace.filters, snapshot_source: "all" },
    deduplication: {
      applied: true,
      input_group_count: 852,
      selected_group_count: 850,
      excluded_group_count: 2
    }
  };

  expect(buildPaperSnapshotReviewCards(allWorkspace).at(-1)).toEqual({
    label: "去重排除",
    value: "2"
  });
  expect(buildPaperSnapshotReviewCards(workspace)).not.toContainEqual({
    label: "去重排除",
    value: "0"
  });
});
```

- [ ] **Step 2：运行 helper 测试确认 RED**

```powershell
Set-Location web
npm test -- paperSnapshotReviewWorkspace.test.ts
```

Expected: FAIL，因为来源选项和新类型尚不存在。

- [ ] **Step 3：扩展 TypeScript 类型和 mock**

在 `PaperSnapshotReviewWorkspace` 增加：

```typescript
  deduplication: {
    applied: boolean;
    input_group_count: number;
    selected_group_count: number;
    excluded_group_count: number;
  };
```

在 groups 增加：

```typescript
    by_snapshot_source: PaperSnapshotReviewGroupSummary[];
```

给 `mockPaperSnapshotReviewWorkspace`、`paperSnapshotReviewWorkspace.test.ts` fixture
和 `apiClient.test.ts` payload 增加具体来源的兼容值：

```typescript
  deduplication: {
    applied: false,
    input_group_count: 850,
    selected_group_count: 850,
    excluded_group_count: 0
  },
```

以及：

```typescript
    by_snapshot_source: [],
```

- [ ] **Step 4：实现集中来源选项和条件指标卡**

在 `paperSnapshotReviewWorkspace.ts` 增加：

```typescript
export const paperSnapshotReviewSourceOptions = [
  { label: "全部来源（All）", value: "all" },
  { label: "historical_backfill", value: "historical_backfill" },
  { label: "manual_record", value: "manual_record" },
  { label: "automation", value: "automation" }
] as const;
```

将 cards 先赋给变量，并在 All 时追加：

```typescript
  if (workspace.filters.snapshot_source === "all") {
    cards.push({
      label: "去重排除",
      value: workspace.deduplication.excluded_group_count.toLocaleString()
    });
  }
  return cards;
```

- [ ] **Step 5：写并运行 API client All 参数测试**

在 `apiClient.test.ts` 新增：

```typescript
it("loads all paper snapshot sources explicitly", async () => {
  const fetchMock = vi.fn(async () => Response.json(apiPayloads["/api/paper-snapshot-review"]));
  vi.stubGlobal("fetch", fetchMock);

  await loadPaperSnapshotReviewWorkspace({ snapshot_source: "all" });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/paper-snapshot-review?snapshot_source=all"
  );
});
```

运行：

```powershell
Set-Location web
npm test -- paperSnapshotReviewWorkspace.test.ts apiClient.test.ts
```

Expected: 两个文件全部 PASS。

- [ ] **Step 6：提交前端契约改动**

```powershell
git add web/src/paperSnapshotReviewWorkspace.ts web/src/paperSnapshotReviewWorkspace.test.ts web/src/apiClient.test.ts web/src/types.ts web/src/mockData.ts
git commit -m "增加推荐快照全部来源选项"
```

## Task 4：页面展示来源与信号数量

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] **Step 1：让页面使用集中来源选项**

从 helper import `paperSnapshotReviewSourceOptions`，替换三个硬编码 option：

```tsx
          <select
            aria-label="快照来源"
            onChange={(event) => onFiltersChange({ snapshot_source: event.target.value })}
            value={filters.snapshot_source}
          >
            {paperSnapshotReviewSourceOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
```

- [ ] **Step 2：增加来源和信号数面板**

在联赛/手数限制区之后增加：

```tsx
      <section className="grid snapshot-review-grid">
        <Panel title="按来源">
          <PaperSnapshotReviewGroupTable groups={workspace.groups.by_snapshot_source} />
        </Panel>
        <Panel title="按信号数">
          <PaperSnapshotReviewGroupTable groups={workspace.groups.by_signal_count} />
        </Panel>
      </section>
```

将页面配置里的副标题从只描述 historical_backfill 改为：

```typescript
subtitle: "按开赛时间回看推荐快照，诊断市场、盘口、手数和策略组合"
```

- [ ] **Step 3：运行前端聚焦测试和构建**

```powershell
Set-Location web
npm test -- paperSnapshotReviewWorkspace.test.ts apiClient.test.ts
npm run build
```

Expected: Vitest 全部 PASS；TypeScript 与 Vite build 成功。

- [ ] **Step 4：提交页面改动**

```powershell
git add web/src/pages/DashboardPage.tsx
git commit -m "展示推荐快照来源分布"
```

## Task 5：完整验证与真实数据冒烟

**Files:**
- Verify only

- [ ] **Step 1：运行后端聚焦测试**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py tests/test_web_console_api.py -q
```

Expected: 全部 PASS。

- [ ] **Step 2：运行完整前端测试和构建**

```powershell
Set-Location web
npm test
npm run build
```

Expected: 全部 Vitest 测试 PASS，build 成功。

- [ ] **Step 3：重启 Web 并查询真实 7 月 All 数据**

```powershell
Set-Location D:\project\IcewinePredictionModel
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart
```

查询：

```powershell
$uri = 'http://127.0.0.1:8000/api/paper-snapshot-review?from_date=2026-07-01T00:00:00&to_date=2026-07-31T23:59:59&snapshot_source=all'
Invoke-RestMethod -Uri $uri | ConvertTo-Json -Depth 6
```

Expected real-data checks:

- `filters.snapshot_source = all`
- `summary.group_count = 288`
- `summary.weighted_roi = -0.0600`
- `deduplication.input_group_count = 288`
- `deduplication.selected_group_count = 288`
- `deduplication.excluded_group_count = 0`
- 来源分布包含 `automation=282`、`manual_record=6`

- [ ] **Step 4：回归具体来源**

显式查询 `snapshot_source=automation`，Expected：7 月仍为 282 组、weighted
ROI `-0.0816`，且 `deduplication.applied=false`。

- [ ] **Step 5：检查范围与工作树**

```powershell
git diff --check
git status --short
git log -6 --oneline
```

Expected：功能提交只包含计划内文件；用户原有 `config/display_names.yaml` 和
未提交的月度回顾文档保持不变。
