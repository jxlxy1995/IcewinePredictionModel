# Paper Automation Task Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Web-managed one-off paper automation task queue that runs odds sync, refreshes paper candidates, batch-records paper recommendations, and pushes Bark messages consistent with the Web paper recommendation record page.

**Architecture:** Add a focused backend task model/service layer, then expose it through FastAPI and a compact React UI. The automation executor reuses existing odds sync, paper queue, paper tracking, and confidence simulation services instead of duplicating business rules. A lightweight Web-backend poller claims due tasks serially and stores execution and Bark results for the dedicated automation task page.

**Tech Stack:** Python 3.12, SQLAlchemy, FastAPI, pytest, React, TypeScript, Vite, existing project `.env` loading.

---

## Source Design

Read first:

- `docs/superpowers/specs/2026-06-15-paper-automation-task-queue-design.md`
- `Agent.md`
- `memory.md`

Key hard constraints:

- Times shown to the user must be Beijing time.
- The task target window uses only match kickoff time, not match-list league/search/status filters.
- Tasks are globally serial.
- Missed-task grace is configurable and defaults to 20 minutes.
- Poll interval defaults to 20 seconds.
- Bark recommendation lines must use the same `confidence_score` and `suggested_stake_units` as Web paper recommendation records, via `build_paper_confidence_workspace(...)`.
- Bark must include every affected recommendation group; split into multiple pushes when the body would exceed the formatter limit.
- Bark failure does not make the main task fail.

## File Structure

Backend files:

- Create `src/icewine_prediction/paper_automation_service.py`
  - Task creation validation.
  - Task claiming/cancellation.
  - Task execution orchestration.
  - Result payload creation.
  - Serialization helpers for API payloads.
- Create `src/icewine_prediction/paper_automation_scheduler.py`
  - Lightweight polling loop.
  - Start/stop lifecycle helpers for FastAPI.
  - Testable single-poll function.
- Create `src/icewine_prediction/bark_notification_service.py`
  - Bark URL loading from environment.
  - Bark HTTP push.
  - Message splitting.
  - Bark-specific return object.
- Create `tests/test_paper_automation_service.py`
  - Data model, validation, execution, and message tests.
- Create `tests/test_paper_automation_scheduler.py`
  - Polling, serial execution, missed grace, and lifecycle tests.

Existing backend files to modify:

- Modify `src/icewine_prediction/models.py`
  - Add `PaperAutomationTask`.
- Modify `src/icewine_prediction/database.py`
  - Add SQLite schema evolution for the `paper_automation_tasks` table.
- Modify `src/icewine_prediction/web_api.py`
  - Wire task service.
  - Add `/api/paper-automation/*` endpoints.
  - Start scheduler when using the real app.
  - Keep tests able to disable scheduler.
- Modify `src/icewine_prediction/notification_service.py`
  - Keep local completion notification untouched.
  - Do not mix Bark into local notification behavior unless importing shared helpers is useful.

Frontend files:

- Modify `web/src/types.ts`
  - Add automation task list/detail types.
- Modify `web/src/apiClient.ts`
  - Add task API calls.
- Modify `web/src/pages/DashboardPage.tsx`
  - Add `automationTasks` view.
  - Add match-list creation dialog.
  - Add automation task page.
- Modify or create `web/src/paperAutomationWorkspace.ts`
  - Formatting helpers for status labels, summary cards, and display rows.
- Modify `web/src/mockData.ts`
  - Add minimal automation task mock data.
- Add tests in `web/src/apiClient.test.ts`.

## Task 1: Add PaperAutomationTask Model And Schema

**Files:**
- Modify: `src/icewine_prediction/models.py`
- Modify: `src/icewine_prediction/database.py`
- Test: `tests/test_paper_automation_service.py`

- [ ] **Step 1: Write failing model/schema tests**

Add `tests/test_paper_automation_service.py`:

```python
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import PaperAutomationTask


BEIJING = ZoneInfo("Asia/Shanghai")


def test_initialize_database_creates_paper_automation_tasks_table():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        task = PaperAutomationTask(
            created_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            updated_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            created_by="web",
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
            match_window_end=datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
            status="pending",
            notification_status="pending",
        )
        session.add(task)
        session.commit()

        loaded = session.get(PaperAutomationTask, task.id)

    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.notification_status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_initialize_database_creates_paper_automation_tasks_table -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `PaperAutomationTask` does not exist.

- [ ] **Step 3: Add SQLAlchemy model**

In `src/icewine_prediction/models.py`, add after `PaperRecommendationRecord`:

```python
class PaperAutomationTask(Base):
    __tablename__ = "paper_automation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False, default="web")
    trigger_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    match_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    match_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notification_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    missed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_payload: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4: Add SQLite schema guard**

In `src/icewine_prediction/database.py`, extend `_ensure_sqlite_schema` so old DBs get the table:

```python
        if "paper_automation_tasks" not in table_names:
            Base.metadata.tables["paper_automation_tasks"].create(connection, checkfirst=True)
```

Place this inside the `with engine.begin() as connection:` block before column checks that depend on existing tables.

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_initialize_database_creates_paper_automation_tasks_table -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/icewine_prediction/models.py src/icewine_prediction/database.py tests/test_paper_automation_service.py
git commit -m "Add paper automation task model"
```

## Task 2: Add Task Creation, Validation, Claiming, And Cancellation Service

**Files:**
- Create: `src/icewine_prediction/paper_automation_service.py`
- Modify: `tests/test_paper_automation_service.py`

- [ ] **Step 1: Add failing service tests**

Append to `tests/test_paper_automation_service.py`:

```python
from datetime import timedelta
from decimal import Decimal

import pytest

from icewine_prediction.models import League, Match, Team
from icewine_prediction.paper_automation_service import (
    PaperAutomationValidationError,
    cancel_paper_automation_task,
    claim_due_paper_automation_task,
    create_paper_automation_task,
)


def _session():
    engine = create_memory_database()
    initialize_database(engine)
    return create_session_factory(engine)()


def _seed_match(session, kickoff: datetime) -> Match:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country="Japan",
        is_enabled=True,
    )
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Yokohama F. Marinos")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Vissel Kobe")
    match = Match(
        source_name="api-football",
        source_match_id="fixture-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        season=2026,
    )
    session.add_all([league, home, away, match])
    session.commit()
    return match


def test_create_task_rejects_empty_match_window():
    now = datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING)
    with _session() as session:
        with pytest.raises(PaperAutomationValidationError, match="没有本地赛程"):
            create_paper_automation_task(
                session,
                trigger_at=now + timedelta(minutes=10),
                match_window_start=now + timedelta(hours=1),
                match_window_end=now + timedelta(hours=1),
                now=now,
            )


def test_create_task_requires_future_trigger_and_existing_match():
    now = datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)

        with pytest.raises(PaperAutomationValidationError, match="未来时间"):
            create_paper_automation_task(
                session,
                trigger_at=now - timedelta(minutes=1),
                match_window_start=kickoff,
                match_window_end=kickoff,
                now=now,
            )


def test_create_task_rejects_duplicate_pending_task():
    now = datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)
        create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        with pytest.raises(PaperAutomationValidationError, match="重复"):
            create_paper_automation_task(
                session,
                trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
                match_window_start=kickoff,
                match_window_end=kickoff,
                now=now,
            )


def test_claim_due_task_marks_missed_after_grace():
    now = datetime(2026, 6, 15, 18, 50, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

        claimed = claim_due_paper_automation_task(session, now=now, grace_minutes=20)

        assert claimed is None
        assert session.get(type(task), task.id).status == "missed"


def test_claim_due_task_sets_running_and_cancel_only_pending():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=now,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

        claimed = claim_due_paper_automation_task(session, now=now, grace_minutes=20)

        assert claimed is not None
        assert claimed.id == task.id
        assert claimed.status == "running"
        with pytest.raises(PaperAutomationValidationError, match="只能取消待执行"):
            cancel_paper_automation_task(session, task.id, now=now)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py -q
```

Expected: FAIL because `paper_automation_service.py` does not exist.

- [ ] **Step 3: Implement service skeleton**

Create `src/icewine_prediction/paper_automation_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_
from sqlalchemy.orm import Session

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.models import Match, PaperAutomationTask


class PaperAutomationValidationError(ValueError):
    pass


def as_beijing_datetime(value: datetime) -> datetime:
    timezone = ZoneInfo(BEIJING_TIMEZONE)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def create_paper_automation_task(
    session: Session,
    *,
    trigger_at: datetime,
    match_window_start: datetime,
    match_window_end: datetime,
    now: datetime,
    created_by: str = "web",
) -> PaperAutomationTask:
    trigger_at = as_beijing_datetime(trigger_at)
    match_window_start = as_beijing_datetime(match_window_start)
    match_window_end = as_beijing_datetime(match_window_end)
    now = as_beijing_datetime(now)
    if trigger_at <= now:
        raise PaperAutomationValidationError("触发任务时间必须是未来时间")
    if match_window_end < match_window_start:
        raise PaperAutomationValidationError("比赛时间段结束时间必须大于或等于开始时间")
    target_count = count_matches_in_window(
        session,
        match_window_start=match_window_start,
        match_window_end=match_window_end,
    )
    if target_count <= 0:
        raise PaperAutomationValidationError(
            "该比赛时间段当前没有本地赛程，请先在比赛列表拉取/确认赛程后再创建自动任务"
        )
    duplicate = (
        session.query(PaperAutomationTask)
        .filter(PaperAutomationTask.status.in_(("pending", "running")))
        .filter(PaperAutomationTask.trigger_at == trigger_at)
        .filter(PaperAutomationTask.match_window_start == match_window_start)
        .filter(PaperAutomationTask.match_window_end == match_window_end)
        .first()
    )
    if duplicate is not None:
        raise PaperAutomationValidationError("已存在相同触发时间和比赛时间段的待执行自动任务")
    task = PaperAutomationTask(
        created_at=now,
        updated_at=now,
        created_by=created_by,
        trigger_at=trigger_at,
        match_window_start=match_window_start,
        match_window_end=match_window_end,
        status="pending",
        notification_status="pending",
    )
    session.add(task)
    session.commit()
    return task


def count_matches_in_window(
    session: Session,
    *,
    match_window_start: datetime,
    match_window_end: datetime,
) -> int:
    return (
        session.query(Match)
        .filter(Match.kickoff_time >= match_window_start)
        .filter(Match.kickoff_time <= match_window_end)
        .count()
    )


def claim_due_paper_automation_task(
    session: Session,
    *,
    now: datetime,
    grace_minutes: int,
) -> PaperAutomationTask | None:
    now = as_beijing_datetime(now)
    running = (
        session.query(PaperAutomationTask)
        .filter(PaperAutomationTask.status == "running")
        .first()
    )
    if running is not None:
        return None
    task = (
        session.query(PaperAutomationTask)
        .filter(PaperAutomationTask.status == "pending")
        .order_by(PaperAutomationTask.trigger_at.asc(), PaperAutomationTask.id.asc())
        .first()
    )
    if task is None or as_beijing_datetime(task.trigger_at) > now:
        return None
    if now > as_beijing_datetime(task.trigger_at) + timedelta(minutes=grace_minutes):
        task.status = "missed"
        task.missed_at = now
        task.updated_at = now
        session.commit()
        return None
    task.status = "running"
    task.started_at = now
    task.updated_at = now
    session.commit()
    return task


def cancel_paper_automation_task(
    session: Session,
    task_id: int,
    *,
    now: datetime,
) -> PaperAutomationTask:
    task = session.get(PaperAutomationTask, task_id)
    if task is None:
        raise PaperAutomationValidationError(f"自动任务不存在: {task_id}")
    if task.status != "pending":
        raise PaperAutomationValidationError("只能取消待执行自动任务")
    now = as_beijing_datetime(now)
    task.status = "cancelled"
    task.cancelled_at = now
    task.updated_at = now
    session.commit()
    return task
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/icewine_prediction/paper_automation_service.py tests/test_paper_automation_service.py
git commit -m "Add paper automation task service"
```

## Task 3: Add Bark Notification And Message Formatting

**Files:**
- Create: `src/icewine_prediction/bark_notification_service.py`
- Modify: `tests/test_paper_automation_service.py`

- [ ] **Step 1: Add failing Bark formatter tests**

Append:

```python
from icewine_prediction.bark_notification_service import (
    BarkPushResult,
    format_paper_automation_bark_messages,
    split_bark_message,
)
from icewine_prediction.paper_confidence_service import PaperConfidenceGroup


def _confidence_group(
    *,
    match_id: int,
    league: str,
    home: str,
    away: str,
    recommendation: str,
    score: int,
    stake: Decimal,
) -> PaperConfidenceGroup:
    return PaperConfidenceGroup(
        group_key=f"{match_id}:asian_handicap:away_cover",
        match_id=match_id,
        source_match_id=str(match_id),
        kickoff_time=datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
        league_name=league,
        league_display_name=league,
        home_team_name=home,
        home_team_display_name=home,
        home_team_logo_url=None,
        home_score=None,
        away_team_name=away,
        away_team_display_name=away,
        away_team_logo_url=None,
        away_score=None,
        market_type="asian_handicap",
        logical_side="away_cover",
        recommendation_text=recommendation,
        representative_record_id=match_id,
        representative_strategy_key="asian_away_cover_hgb_edge_v1",
        representative_market_line=Decimal("-0.50"),
        representative_odds=Decimal("1.930"),
        signal_record_ids=(match_id,),
        triggered_strategy_keys=("asian_away_cover_hgb_edge_v1",),
        triggered_strategy_display_names=("客队HGB边际",),
        signal_families=("asian_away_hgb",),
        confidence_score=score,
        suggested_stake_units=stake,
        stake_cap_reason="none",
        status="pending",
        settlement_result=None,
        flat_profit_units=Decimal("0.000"),
        weighted_profit_units=Decimal("0.000"),
        warning=None,
    )


def test_format_bark_messages_includes_all_confidence_groups():
    groups = [
        _confidence_group(
            match_id=1,
            league="日职联",
            home="横滨水手",
            away="神户胜利船",
            recommendation="客队 +0.50",
            score=80,
            stake=Decimal("1.50"),
        ),
        _confidence_group(
            match_id=2,
            league="韩K",
            home="蔚山HD",
            away="首尔FC",
            recommendation="小 2.50",
            score=76,
            stake=Decimal("1.00"),
        ),
    ]

    messages = format_paper_automation_bark_messages(
        title_prefix="纸面自动任务",
        window_label="18:30 - 18:30",
        odds_summary="回填：2场 成功2 失败0",
        candidate_count=2,
        created_group_count=2,
        groups=groups,
        max_body_chars=1000,
    )

    combined = "\n".join(message.body for message in messages)
    assert "横滨水手 vs 神户胜利船" in combined
    assert "评分80  推荐1.50手" in combined
    assert "蔚山HD vs 首尔FC" in combined
    assert "评分76  推荐1.00手" in combined


def test_format_bark_messages_splits_without_dropping_groups():
    groups = [
        _confidence_group(
            match_id=index,
            league="日职联",
            home=f"主队{index}",
            away=f"客队{index}",
            recommendation="客队 +0.50",
            score=70 + index,
            stake=Decimal("1.00"),
        )
        for index in range(1, 8)
    ]

    messages = format_paper_automation_bark_messages(
        title_prefix="纸面自动任务",
        window_label="18:30 - 18:30",
        odds_summary="回填：7场 成功7 失败0",
        candidate_count=7,
        created_group_count=7,
        groups=groups,
        max_body_chars=180,
    )

    combined = "\n".join(message.body for message in messages)
    assert len(messages) > 1
    for index in range(1, 8):
        assert f"主队{index} vs 客队{index}" in combined
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_format_bark_messages_includes_all_confidence_groups tests/test_paper_automation_service.py::test_format_bark_messages_splits_without_dropping_groups -q
```

Expected: FAIL because `bark_notification_service.py` does not exist.

- [ ] **Step 3: Implement Bark message service**

Create `src/icewine_prediction/bark_notification_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class BarkMessage:
    title: str
    body: str


@dataclass(frozen=True)
class BarkPushResult:
    sent: bool
    status_code: int | None = None
    error: str | None = None


def load_bark_push_url() -> str | None:
    value = os.environ.get("BARK_PUSH_URL")
    return value.strip() if value and value.strip() else None


def push_bark_message(push_url: str, message: BarkMessage, *, timeout_seconds: float = 8.0) -> BarkPushResult:
    try:
        response = requests.post(
            push_url,
            json={"title": message.title, "body": message.body},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return BarkPushResult(sent=False, error=str(exc))
    if 200 <= response.status_code < 300:
        return BarkPushResult(sent=True, status_code=response.status_code)
    return BarkPushResult(sent=False, status_code=response.status_code, error=response.text[:500])


def format_paper_automation_bark_messages(
    *,
    title_prefix: str,
    window_label: str,
    odds_summary: str,
    candidate_count: int,
    created_group_count: int,
    groups,
    max_body_chars: int = 1800,
) -> list[BarkMessage]:
    if not groups:
        title = f"{title_prefix}：无候选"
        body = "\n".join(
            [
                f"窗口：{window_label}",
                odds_summary,
                f"候选：{candidate_count} 记录：0",
            ]
        )
        return [BarkMessage(title=title, body=body)]
    lines = [
        f"窗口：{window_label}",
        odds_summary,
        f"候选：{candidate_count} 记录组：{created_group_count}",
        "",
    ]
    group_blocks = [_format_group_line(index, group) for index, group in enumerate(groups, start=1)]
    return _split_group_blocks(
        title_prefix=title_prefix,
        created_group_count=created_group_count,
        header_lines=lines,
        group_blocks=group_blocks,
        max_body_chars=max_body_chars,
    )


def _format_group_line(index: int, group) -> str:
    kickoff = str(group.kickoff_time).replace("T", " ")[11:16]
    league = group.league_display_name or group.league_name
    home = group.home_team_display_name or group.home_team_name
    away = group.away_team_display_name or group.away_team_name
    recommendation = group.recommendation_text or "-"
    return (
        f"{index}. {league} {home} vs {away}\n"
        f"   {kickoff} {recommendation}  评分{group.confidence_score}  "
        f"推荐{group.suggested_stake_units}手"
    )


def _split_group_blocks(
    *,
    title_prefix: str,
    created_group_count: int,
    header_lines: list[str],
    group_blocks: list[str],
    max_body_chars: int,
) -> list[BarkMessage]:
    parts: list[list[str]] = []
    current = list(header_lines)
    for block in group_blocks:
        candidate = current + ([block] if current[-1] == "" else ["", block])
        if len("\n".join(candidate)) > max_body_chars and len(current) > len(header_lines):
            parts.append(current)
            current = list(header_lines) + [block]
        else:
            current = candidate
    if len(current) > len(header_lines):
        parts.append(current)
    total_parts = len(parts)
    return [
        BarkMessage(
            title=(
                f"{title_prefix}：已记录 {created_group_count} 条"
                if total_parts == 1
                else f"{title_prefix}：已记录 {created_group_count} 条（{index}/{total_parts}）"
            ),
            body="\n".join(part),
        )
        for index, part in enumerate(parts, start=1)
    ]
```

- [ ] **Step 4: Run Bark formatter tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_format_bark_messages_includes_all_confidence_groups tests/test_paper_automation_service.py::test_format_bark_messages_splits_without_dropping_groups -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/icewine_prediction/bark_notification_service.py tests/test_paper_automation_service.py
git commit -m "Add Bark formatting for paper automation"
```

## Task 4: Add Task Execution Workflow

**Files:**
- Modify: `src/icewine_prediction/paper_automation_service.py`
- Modify: `tests/test_paper_automation_service.py`

- [ ] **Step 1: Add failing execution test with injected collaborators**

Append:

```python
from icewine_prediction.paper_automation_service import execute_paper_automation_task


def test_execute_task_continues_after_partial_odds_failure_and_sends_bark():
    now = datetime(2026, 6, 15, 18, 22, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []

    with _session() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )
        task.status = "running"
        session.commit()

        def fake_odds_sync(match_ids):
            return {
                "success": [{"match_id": match_ids[0], "message": "赔率已刷新"}],
                "failed": [],
                "skipped": [],
                "requests": 1,
            }

        def fake_queue_builder(session, task):
            return type(
                "Report",
                (),
                {
                    "total_matches": 1,
                    "candidate_count": 0,
                    "status_counts": {"no_odds": 1},
                    "discarded_by_robustness_match_count": 0,
                    "rows": [],
                },
            )()

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=fake_odds_sync,
            queue_builder=fake_queue_builder,
            bark_push_url="https://example.test/bark",
            bark_sender=lambda url, message: sent_messages.append((url, message)) or BarkPushResult(sent=True),
        )

        reloaded = session.get(PaperAutomationTask, task.id)

    assert result.status == "success"
    assert reloaded.status == "success"
    assert reloaded.notification_status == "sent"
    assert sent_messages
    assert "无候选" in sent_messages[0][1].title
```

- [ ] **Step 2: Run execution test to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_execute_task_continues_after_partial_odds_failure_and_sends_bark -q
```

Expected: FAIL because `execute_paper_automation_task` does not exist.

- [ ] **Step 3: Implement minimal execution flow with injection points**

In `paper_automation_service.py`, add imports:

```python
import json

from icewine_prediction.bark_notification_service import (
    BarkMessage,
    BarkPushResult,
    format_paper_automation_bark_messages,
    load_bark_push_url,
    push_bark_message,
)
from icewine_prediction.paper_confidence_service import build_paper_confidence_workspace
from icewine_prediction.paper_recommendation_tracking_service import (
    build_paper_tracking_workspace,
    create_paper_record_from_queue_row,
)
```

Add:

```python
@dataclass(frozen=True)
class PaperAutomationExecutionResult:
    status: str
    notification_status: str
    result_payload: dict[str, Any]


def execute_paper_automation_task(
    session: Session,
    task_id: int,
    *,
    now: datetime,
    odds_syncer,
    queue_builder,
    bark_push_url: str | None = None,
    bark_sender=push_bark_message,
) -> PaperAutomationExecutionResult:
    task = session.get(PaperAutomationTask, task_id)
    if task is None:
        raise PaperAutomationValidationError(f"自动任务不存在: {task_id}")
    now = as_beijing_datetime(now)
    try:
        match_ids = _target_match_ids(session, task)
        odds_result = odds_syncer(match_ids)
        queue_report = queue_builder(session, task)
        created_record_ids, skipped = _record_queue_candidates(session, queue_report, recorded_at=now)
        groups = _confidence_groups_for_records(session, created_record_ids)
        messages = format_paper_automation_bark_messages(
            title_prefix="纸面自动任务",
            window_label=_window_label(task),
            odds_summary=_odds_summary_text(match_ids, odds_result),
            candidate_count=int(getattr(queue_report, "candidate_count", 0)),
            created_group_count=len(groups),
            groups=groups,
        )
        notification_status, notification_error = _send_bark_messages(
            messages,
            bark_push_url=bark_push_url if bark_push_url is not None else load_bark_push_url(),
            bark_sender=bark_sender,
        )
        payload = {
            "target_match_ids": match_ids,
            "odds": odds_result,
            "queue": {
                "total_matches": getattr(queue_report, "total_matches", 0),
                "candidate_count": getattr(queue_report, "candidate_count", 0),
                "status_counts": getattr(queue_report, "status_counts", {}),
                "discarded_by_robustness_match_count": getattr(
                    queue_report,
                    "discarded_by_robustness_match_count",
                    0,
                ),
            },
            "batch_record": {
                "created_record_ids": created_record_ids,
                "created_count": len(created_record_ids),
                "skipped": skipped,
                "skipped_count": len(skipped),
            },
            "bark": {
                "messages": [{"title": item.title, "body": item.body} for item in messages],
            },
        }
        task.status = "success"
        task.notification_status = notification_status
        task.notification_error = notification_error
        task.result_payload = json.dumps(payload, ensure_ascii=False)
        task.finished_at = now
        task.updated_at = now
        session.commit()
        return PaperAutomationExecutionResult("success", notification_status, payload)
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        task.finished_at = now
        task.updated_at = now
        session.commit()
        raise


def _target_match_ids(session: Session, task: PaperAutomationTask) -> list[int]:
    rows = (
        session.query(Match.id)
        .filter(Match.kickoff_time >= task.match_window_start)
        .filter(Match.kickoff_time <= task.match_window_end)
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )
    return [int(row[0]) for row in rows]


def _record_queue_candidates(session: Session, queue_report, *, recorded_at: datetime) -> tuple[list[int], list[dict[str, Any]]]:
    created_record_ids = []
    skipped = []
    for row in getattr(queue_report, "rows", []):
        if row.status != "candidate":
            continue
        try:
            record = create_paper_record_from_queue_row(session, row, recorded_at=recorded_at)
        except ValueError as exc:
            skipped.append({"match_id": row.match_id, "strategy_key": row.strategy_key, "reason": str(exc)})
            continue
        created_record_ids.append(record.id)
    return created_record_ids, skipped


def _confidence_groups_for_records(session: Session, created_record_ids: list[int]):
    workspace = build_paper_tracking_workspace(session, candidates=[])
    confidence = build_paper_confidence_workspace(workspace.records)
    created_set = set(created_record_ids)
    return [
        group
        for group in confidence.groups
        if created_set.intersection(group.signal_record_ids)
    ]


def _send_bark_messages(messages: list[BarkMessage], *, bark_push_url: str | None, bark_sender) -> tuple[str, str | None]:
    if not bark_push_url:
        return "not_configured", None
    errors = []
    for message in messages:
        result = bark_sender(bark_push_url, message)
        if not result.sent:
            errors.append(result.error or f"status={result.status_code}")
    if errors:
        return "failed", "; ".join(errors)
    return "sent", None


def _window_label(task: PaperAutomationTask) -> str:
    return f"{task.match_window_start:%H:%M} - {task.match_window_end:%H:%M}"


def _odds_summary_text(match_ids: list[int], odds_result: dict[str, Any]) -> str:
    success = len(odds_result.get("success", []))
    failed = len(odds_result.get("failed", []))
    skipped = len(odds_result.get("skipped", []))
    return f"回填：{len(match_ids)}场 成功{success} 失败{failed} 跳过{skipped}"
```

- [ ] **Step 4: Run execution test**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py::test_execute_task_continues_after_partial_odds_failure_and_sends_bark -q
```

Expected: PASS.

- [ ] **Step 5: Add real queue builder wrapper**

In `paper_automation_service.py`, add:

```python
def build_real_paper_queue_for_task(session: Session, task: PaperAutomationTask, *, now: datetime, scorer=None, display_name_service=None):
    from icewine_prediction.paper_recommendation_queue_service import build_paper_recommendation_queue

    return build_paper_recommendation_queue(
        session,
        now=now,
        start_time=task.match_window_start,
        end_time=task.match_window_end,
        scorer=scorer,
        display_name_service=display_name_service,
    )
```

- [ ] **Step 6: Run full backend automation tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/icewine_prediction/paper_automation_service.py tests/test_paper_automation_service.py
git commit -m "Add paper automation execution flow"
```

## Task 5: Add Scheduler Poller

**Files:**
- Create: `src/icewine_prediction/paper_automation_scheduler.py`
- Create: `tests/test_paper_automation_scheduler.py`

- [ ] **Step 1: Add scheduler tests**

Create `tests/test_paper_automation_scheduler.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import League, Match, PaperAutomationTask, Team
from icewine_prediction.paper_automation_scheduler import poll_paper_automation_once
from icewine_prediction.paper_automation_service import create_paper_automation_task


BEIJING = ZoneInfo("Asia/Shanghai")


def _session_factory():
    engine = create_memory_database()
    initialize_database(engine)
    return create_session_factory(engine)


def _seed_match(session, kickoff):
    league = League(source_name="api-football", source_league_id="98", name="J1 League", country="Japan", is_enabled=True)
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Home")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Away")
    match = Match(
        source_name="api-football",
        source_match_id="fixture",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        season=2026,
    )
    session.add_all([league, home, away, match])
    session.commit()


def test_poll_runs_one_due_task_and_keeps_serial_execution():
    session_factory = _session_factory()
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    executed = []
    with session_factory() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=now,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

    poll_paper_automation_once(
        session_factory,
        now=now,
        grace_minutes=20,
        executor=lambda task_id: executed.append(task_id),
    )

    with session_factory() as session:
        loaded = session.get(PaperAutomationTask, task.id)

    assert executed == [task.id]
    assert loaded.status == "running"


def test_poll_marks_overdue_task_missed():
    session_factory = _session_factory()
    trigger = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with session_factory() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=trigger,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

    poll_paper_automation_once(
        session_factory,
        now=trigger + timedelta(minutes=21),
        grace_minutes=20,
        executor=lambda task_id: None,
    )

    with session_factory() as session:
        loaded = session.get(PaperAutomationTask, task.id)

    assert loaded.status == "missed"
```

- [ ] **Step 2: Run scheduler tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_scheduler.py -q
```

Expected: FAIL because scheduler module does not exist.

- [ ] **Step 3: Implement scheduler module**

Create `src/icewine_prediction/paper_automation_scheduler.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Event, Thread
from time import sleep
from typing import Callable

from sqlalchemy.orm import Session

from icewine_prediction.paper_automation_service import claim_due_paper_automation_task
from icewine_prediction.time_utils import now_beijing


def poll_paper_automation_once(
    session_factory: Callable[[], Session],
    *,
    now: datetime,
    grace_minutes: int,
    executor: Callable[[int], None],
) -> int | None:
    with session_factory() as session:
        task = claim_due_paper_automation_task(session, now=now, grace_minutes=grace_minutes)
        if task is None:
            return None
        task_id = task.id
    executor(task_id)
    return task_id


@dataclass
class PaperAutomationScheduler:
    session_factory: Callable[[], Session]
    executor: Callable[[int], None]
    grace_minutes: int = 20
    poll_seconds: int = 20
    clock: Callable[[], datetime] = now_beijing

    def __post_init__(self) -> None:
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run, name="paper-automation-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                poll_paper_automation_once(
                    self.session_factory,
                    now=self.clock(),
                    grace_minutes=self.grace_minutes,
                    executor=self.executor,
                )
            except Exception:
                pass
            self._stop_event.wait(self.poll_seconds)
```

- [ ] **Step 4: Run scheduler tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_scheduler.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/icewine_prediction/paper_automation_scheduler.py tests/test_paper_automation_scheduler.py
git commit -m "Add paper automation scheduler"
```

## Task 6: Add Web API Endpoints

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `src/icewine_prediction/paper_automation_service.py`
- Modify: `tests/test_web_console_api.py`

- [ ] **Step 1: Add API tests**

Append focused tests to `tests/test_web_console_api.py` using existing app fixtures/patterns in that file:

```python
def test_web_console_api_creates_paper_automation_task(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    app = create_web_app(
        session_factory=session_factory,
        clock=lambda: datetime(2026, 5, 20, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_paper_automation_scheduler=False,
    )
    client = TestClient(app)

    response = client.post(
        "/api/paper-automation/tasks",
        json={
            "trigger_at": "2026-05-20T21:30",
            "match_window_start": "2026-05-20T22:00",
            "match_window_end": "2026-05-20T22:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["target_match_count"] == 1


def test_web_console_api_rejects_empty_paper_automation_window(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    app = create_web_app(
        session_factory=session_factory,
        clock=lambda: datetime(2026, 6, 15, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_paper_automation_scheduler=False,
    )
    client = TestClient(app)

    response = client.post(
        "/api/paper-automation/tasks",
        json={
            "trigger_at": "2026-06-15T18:21",
            "match_window_start": "2026-06-15T18:30",
            "match_window_end": "2026-06-15T18:30",
        },
    )

    assert response.status_code == 400
    assert "没有本地赛程" in response.json()["detail"]
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_creates_paper_automation_task tests/test_web_console_api.py::test_web_console_api_rejects_empty_paper_automation_window -q
```

Expected: FAIL because `start_paper_automation_scheduler` parameter and endpoints do not exist.

- [ ] **Step 3: Add service payload helpers**

In `paper_automation_service.py`, add:

```python
def build_paper_automation_task_payload(session: Session, task: PaperAutomationTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "created_at": _format_dt(task.created_at),
        "updated_at": _format_dt(task.updated_at),
        "created_by": task.created_by,
        "trigger_at": _format_dt(task.trigger_at),
        "match_window_start": _format_dt(task.match_window_start),
        "match_window_end": _format_dt(task.match_window_end),
        "status": task.status,
        "notification_status": task.notification_status,
        "notification_error": task.notification_error,
        "started_at": _format_dt(task.started_at),
        "finished_at": _format_dt(task.finished_at),
        "missed_at": _format_dt(task.missed_at),
        "cancelled_at": _format_dt(task.cancelled_at),
        "error_message": task.error_message,
        "target_match_count": count_matches_in_window(
            session,
            match_window_start=task.match_window_start,
            match_window_end=task.match_window_end,
        ),
        "result_payload": json.loads(task.result_payload) if task.result_payload else None,
    }


def list_paper_automation_tasks(session: Session, *, limit: int = 100) -> list[PaperAutomationTask]:
    return (
        session.query(PaperAutomationTask)
        .order_by(PaperAutomationTask.trigger_at.desc(), PaperAutomationTask.id.desc())
        .limit(limit)
        .all()
    )


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_beijing_datetime(value).isoformat()
```

- [ ] **Step 4: Wire endpoints**

In `web_api.py`:

1. Import:

```python
from icewine_prediction.paper_automation_service import (
    PaperAutomationValidationError,
    build_paper_automation_task_payload,
    cancel_paper_automation_task,
    create_paper_automation_task,
    list_paper_automation_tasks,
)
```

2. Add `start_paper_automation_scheduler: bool = True` to `create_web_app(...)`.

3. Add endpoints near paper recommendation routes:

```python
    @app.get("/api/paper-automation/tasks")
    def paper_automation_tasks() -> list[dict[str, Any]]:
        with session_factory() as session:
            return [
                build_paper_automation_task_payload(session, task)
                for task in list_paper_automation_tasks(session)
            ]

    @app.post("/api/paper-automation/tasks")
    def create_paper_automation_task_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            trigger_at = _parse_optional_datetime(payload.get("trigger_at"))
            match_window_start = _parse_optional_datetime(payload.get("match_window_start"))
            match_window_end = _parse_optional_datetime(payload.get("match_window_end"))
            if trigger_at is None or match_window_start is None or match_window_end is None:
                raise PaperAutomationValidationError("自动任务需要触发时间和比赛时间段")
            with session_factory() as session:
                task = create_paper_automation_task(
                    session,
                    trigger_at=trigger_at,
                    match_window_start=match_window_start,
                    match_window_end=match_window_end,
                    now=clock(),
                )
                return build_paper_automation_task_payload(session, task)
        except PaperAutomationValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/paper-automation/tasks/{task_id}")
    def paper_automation_task_detail(task_id: int) -> dict[str, Any]:
        with session_factory() as session:
            task = session.get(PaperAutomationTask, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="自动任务不存在")
            return build_paper_automation_task_payload(session, task)

    @app.post("/api/paper-automation/tasks/{task_id}/cancel")
    def cancel_paper_automation_task_endpoint(task_id: int) -> dict[str, Any]:
        try:
            with session_factory() as session:
                task = cancel_paper_automation_task(session, task_id, now=clock())
                return build_paper_automation_task_payload(session, task)
        except PaperAutomationValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
```

4. Add `PaperAutomationTask` to models import.

- [ ] **Step 5: Run API tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_creates_paper_automation_task tests/test_web_console_api.py::test_web_console_api_rejects_empty_paper_automation_window -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/icewine_prediction/web_api.py src/icewine_prediction/paper_automation_service.py tests/test_web_console_api.py
git commit -m "Add paper automation API"
```

## Task 7: Wire Real Scheduler Execution Into Web App

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `src/icewine_prediction/paper_automation_service.py`
- Test: `tests/test_web_console_api.py`

- [ ] **Step 1: Add test that scheduler can be disabled in API tests**

Add this assertion:

```python
def test_web_app_can_disable_paper_automation_scheduler():
    app = create_web_app(start_paper_automation_scheduler=False)
    assert app.title == "Icewine Prediction Console API"
```

- [ ] **Step 2: Run test**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_web_console_api.py::test_web_app_can_disable_paper_automation_scheduler -q
```

Expected: PASS after Task 6.

- [ ] **Step 3: Add real executor closure in `web_api.py`**

In `create_web_app`, after syncer defaults are resolved, create:

```python
    def execute_paper_automation_task_by_id(task_id: int) -> None:
        with session_factory() as session:
            execute_paper_automation_task(
                session,
                task_id,
                now=clock(),
                odds_syncer=match_list_odds_syncer,
                queue_builder=lambda queue_session, task: build_real_paper_queue_for_task(
                    queue_session,
                    task,
                    now=clock(),
                    scorer=paper_queue_scorer,
                    display_name_service=display_name_service,
                ),
            )
```

Import `execute_paper_automation_task` and `build_real_paper_queue_for_task`.

- [ ] **Step 4: Start scheduler on app startup**

In `web_api.py`, import:

```python
import os
from icewine_prediction.paper_automation_scheduler import PaperAutomationScheduler
```

Add helper:

```python
def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
```

Inside `create_web_app`, after endpoints or before return:

```python
    if start_paper_automation_scheduler:
        scheduler = PaperAutomationScheduler(
            session_factory=session_factory,
            executor=execute_paper_automation_task_by_id,
            grace_minutes=_int_env("PAPER_AUTOMATION_GRACE_MINUTES", 20),
            poll_seconds=_int_env("PAPER_AUTOMATION_POLL_SECONDS", 20),
            clock=clock,
        )

        @app.on_event("startup")
        def start_paper_automation_scheduler_event() -> None:
            scheduler.start()

        @app.on_event("shutdown")
        def stop_paper_automation_scheduler_event() -> None:
            scheduler.stop()
```

- [ ] **Step 5: Run focused backend tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py tests/test_paper_automation_scheduler.py tests/test_web_console_api.py::test_web_app_can_disable_paper_automation_scheduler -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/icewine_prediction/web_api.py src/icewine_prediction/paper_automation_service.py tests/test_web_console_api.py
git commit -m "Wire paper automation scheduler into web app"
```

## Task 8: Add Frontend API Types And Client Calls

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/apiClient.test.ts`

- [ ] **Step 1: Add failing apiClient test**

In `web/src/apiClient.test.ts`, add:

```typescript
import { createPaperAutomationTask, loadPaperAutomationTasks } from "./apiClient";

it("creates paper automation tasks", async () => {
  fetchMock.mockResolvedValueOnce(
    Response.json({
      id: 1,
      trigger_at: "2026-06-15T18:21:00+08:00",
      match_window_start: "2026-06-15T18:30:00+08:00",
      match_window_end: "2026-06-15T18:30:00+08:00",
      status: "pending",
      notification_status: "pending",
      target_match_count: 3,
      updated_at: "2026-06-15T17:00:00+08:00"
    })
  );

  await createPaperAutomationTask({
    trigger_at: "2026-06-15T18:21",
    match_window_start: "2026-06-15T18:30",
    match_window_end: "2026-06-15T18:30"
  });

  expect(fetchMock).toHaveBeenCalledWith("/api/paper-automation/tasks", {
    body: JSON.stringify({
      trigger_at: "2026-06-15T18:21",
      match_window_start: "2026-06-15T18:30",
      match_window_end: "2026-06-15T18:30"
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST"
  });
});
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```powershell
cd web
npm test -- --run apiClient.test.ts
```

Expected: FAIL because exported functions/types do not exist.

- [ ] **Step 3: Add TypeScript types**

In `web/src/types.ts`, add:

```typescript
export type PaperAutomationTask = {
  id: number;
  created_at?: string | null;
  updated_at: string;
  created_by?: string;
  trigger_at: string;
  match_window_start: string;
  match_window_end: string;
  status: string;
  notification_status: string;
  notification_error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  missed_at?: string | null;
  cancelled_at?: string | null;
  error_message?: string | null;
  target_match_count: number;
  result_payload?: PaperAutomationTaskResult | null;
};

export type PaperAutomationTaskResult = {
  target_match_ids?: number[];
  odds?: unknown;
  queue?: {
    total_matches: number;
    candidate_count: number;
    status_counts: Record<string, number>;
    discarded_by_robustness_match_count: number;
  };
  batch_record?: {
    created_record_ids: number[];
    created_count: number;
    skipped_count: number;
    skipped: Array<{ match_id: number | null; strategy_key: string | null; reason: string }>;
  };
  bark?: {
    messages: Array<{ title: string; body: string }>;
  };
};

export type CreatePaperAutomationTaskPayload = {
  trigger_at: string;
  match_window_start: string;
  match_window_end: string;
};
```

- [ ] **Step 4: Add API client functions**

In `web/src/apiClient.ts`, import types and add:

```typescript
export async function loadPaperAutomationTasks(): Promise<PaperAutomationTask[]> {
  return await getJsonOrFallback<PaperAutomationTask[]>("/api/paper-automation/tasks", []);
}

export async function createPaperAutomationTask(
  payload: CreatePaperAutomationTaskPayload
): Promise<PaperAutomationTask> {
  return await postJson<PaperAutomationTask>("/api/paper-automation/tasks", payload);
}

export async function loadPaperAutomationTask(taskId: number): Promise<PaperAutomationTask> {
  return await getJson<PaperAutomationTask>(`/api/paper-automation/tasks/${taskId}`);
}

export async function cancelPaperAutomationTask(taskId: number): Promise<PaperAutomationTask> {
  return await postJson<PaperAutomationTask>(`/api/paper-automation/tasks/${taskId}/cancel`, {});
}
```

- [ ] **Step 5: Run frontend API test**

Run:

```powershell
cd web
npm test -- --run apiClient.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/types.ts web/src/apiClient.ts web/src/apiClient.test.ts
git commit -m "Add paper automation API client"
```

## Task 9: Add Match List Creation Dialog

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/styles.css`
- Test: `npm run build`

- [ ] **Step 1: Add state and imports**

In `DashboardPage.tsx`, import:

```typescript
  createPaperAutomationTask,
  loadPaperAutomationTasks,
```

Add state near match-list state:

```typescript
  const [paperAutomationTasks, setPaperAutomationTasks] = useState<PaperAutomationTask[]>([]);
  const [automationDialogOpen, setAutomationDialogOpen] = useState(false);
  const [automationDraft, setAutomationDraft] = useState({
    trigger_at: "",
    match_window_start: "",
    match_window_end: ""
  });
  const [automationMessage, setAutomationMessage] = useState<string | null>(null);
  const [automationError, setAutomationError] = useState<string | null>(null);
```

Import `PaperAutomationTask` from `../types`.

- [ ] **Step 2: Add button to match list view props**

Extend `FilteredMatchListView` props:

```typescript
  onCreateAutomationTask: () => void;
```

Add a button in the existing match-list action toolbar:

```tsx
<button disabled={actionInFlight !== null} onClick={onCreateAutomationTask} type="button">
  <Clock size={16} />
  创建自动任务
</button>
```

Use a lucide icon already imported or add `Clock`.

- [ ] **Step 3: Add modal component inside DashboardPage.tsx**

Add:

```tsx
function PaperAutomationTaskDialog({
  draft,
  errorText,
  isOpen,
  messageText,
  onClose,
  onDraftChange,
  onSubmit
}: {
  draft: { trigger_at: string; match_window_start: string; match_window_end: string };
  errorText: string | null;
  isOpen: boolean;
  messageText: string | null;
  onClose: () => void;
  onDraftChange: (draft: Partial<{ trigger_at: string; match_window_start: string; match_window_end: string }>) => void;
  onSubmit: () => void;
}) {
  if (!isOpen) {
    return null;
  }
  return (
    <div className="modal-backdrop">
      <section className="modal-panel">
        <header className="modal-header">
          <h2>创建一次性自动任务</h2>
          <button onClick={onClose} type="button">关闭</button>
        </header>
        <p className="muted-text">
          到触发时间后自动执行赔率回填、刷新候选、批量记录候选，并推送 Bark。
        </p>
        {messageText && <div className="inline-success">{messageText}</div>}
        {errorText && <div className="inline-warning">{errorText}</div>}
        <label>
          <span>触发任务时间</span>
          <input
            onChange={(event) => onDraftChange({ trigger_at: event.target.value })}
            type="datetime-local"
            value={draft.trigger_at}
          />
        </label>
        <label>
          <span>筛选比赛开始时间</span>
          <input
            onChange={(event) => onDraftChange({ match_window_start: event.target.value })}
            type="datetime-local"
            value={draft.match_window_start}
          />
        </label>
        <label>
          <span>筛选比赛结束时间</span>
          <input
            onChange={(event) => onDraftChange({ match_window_end: event.target.value })}
            type="datetime-local"
            value={draft.match_window_end}
          />
        </label>
        <div className="dialog-actions">
          <button onClick={onClose} type="button">取消</button>
          <button onClick={onSubmit} type="button">保存任务</button>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire submit handler**

In `DashboardPage`, pass:

```tsx
onCreateAutomationTask={() => {
  setAutomationError(null);
  setAutomationMessage(null);
  setAutomationDraft({
    trigger_at: "",
    match_window_start: matchListFilters.start_time,
    match_window_end: matchListFilters.end_time
  });
  setAutomationDialogOpen(true);
}}
```

Render dialog near the end of `<main>`:

```tsx
<PaperAutomationTaskDialog
  draft={automationDraft}
  errorText={automationError}
  isOpen={automationDialogOpen}
  messageText={automationMessage}
  onClose={() => setAutomationDialogOpen(false)}
  onDraftChange={(draft) => setAutomationDraft((current) => ({ ...current, ...draft }))}
  onSubmit={() => {
    setAutomationError(null);
    setAutomationMessage(null);
    createPaperAutomationTask(automationDraft)
      .then((task) => {
        setPaperAutomationTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
        setAutomationMessage(`自动任务已创建，将于 ${formatShortDateTime(task.trigger_at)} 执行`);
      })
      .catch((error) => setAutomationError(formatActionError("创建自动任务失败", error)));
  }}
/>
```

- [ ] **Step 5: Add modal CSS classes**

In `web/src/styles.css`, add:

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

.modal-panel {
  background: #fff;
  border: 1px solid #d7dde7;
  border-radius: 8px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
  display: grid;
  gap: 12px;
  max-width: 520px;
  padding: 18px;
  width: min(520px, calc(100vw - 32px));
}

.modal-header,
.dialog-actions {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/pages/DashboardPage.tsx web/src/styles.css
git commit -m "Add paper automation creation dialog"
```

## Task 10: Add Automation Task Page

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`
- Create: `web/src/paperAutomationWorkspace.ts`
- Modify: `web/src/mockData.ts`
- Test: frontend build and focused tests

- [ ] **Step 1: Add view key and nav item**

In `DashboardPage.tsx`, add `automationTasks` to `ViewKey`.

Add nav item after match list:

```typescript
{ key: "automationTasks", label: "自动任务", icon: Clock }
```

Add view text:

```typescript
automationTasks: {
  title: "自动任务",
  subtitle: "查看一次性纸面自动任务的执行状态、Bark 推送和失败诊断"
}
```

- [ ] **Step 2: Create formatting helper**

Create `web/src/paperAutomationWorkspace.ts`:

```typescript
import type { PaperAutomationTask } from "./types";

export function buildPaperAutomationSummary(tasks: PaperAutomationTask[]) {
  const today = new Date().toISOString().slice(0, 10);
  return {
    pending: tasks.filter((task) => task.status === "pending").length,
    running: tasks.filter((task) => task.status === "running").length,
    completedToday: tasks.filter(
      (task) => task.status === "success" && task.finished_at?.startsWith(today)
    ).length,
    failedOrBarkFailed: tasks.filter(
      (task) => task.status === "failed" || task.notification_status === "failed"
    ).length
  };
}

export function formatAutomationStatus(status: string): string {
  const labels: Record<string, string> = {
    pending: "待执行",
    running: "执行中",
    success: "成功",
    failed: "失败",
    missed: "已错过",
    cancelled: "已取消"
  };
  return labels[status] ?? status;
}

export function formatNotificationStatus(status: string): string {
  const labels: Record<string, string> = {
    not_configured: "Bark未配置",
    pending: "待推送",
    sent: "已推送",
    failed: "Bark失败",
    skipped: "已跳过"
  };
  return labels[status] ?? status;
}
```

- [ ] **Step 3: Add page component**

In `DashboardPage.tsx`, add:

```tsx
function PaperAutomationTaskView({
  tasks,
  onCancel,
  onRefresh
}: {
  tasks: PaperAutomationTask[];
  onCancel: (task: PaperAutomationTask) => void;
  onRefresh: () => void;
}) {
  const summary = buildPaperAutomationSummary(tasks);
  return (
    <section className="single-column">
      <section className="metrics compact-metrics">
        <MetricCard label="待执行" value={summary.pending.toLocaleString()} />
        <MetricCard label="执行中" value={summary.running.toLocaleString()} />
        <MetricCard label="今日完成" value={summary.completedToday.toLocaleString()} />
        <MetricCard label="失败/Bark失败" value={summary.failedOrBarkFailed.toLocaleString()} tone="warning" />
      </section>
      <Panel title="自动任务">
        <div className="table-toolbar">
          <button onClick={onRefresh} type="button">刷新</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>触发时间</th>
              <th>比赛时间段</th>
              <th>状态</th>
              <th>比赛</th>
              <th>Bark</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td>{formatShortDateTime(task.trigger_at)}</td>
                <td>{`${formatShortDateTime(task.match_window_start)} - ${formatShortDateTime(task.match_window_end)}`}</td>
                <td>{formatAutomationStatus(task.status)}</td>
                <td>{task.target_match_count}</td>
                <td>{formatNotificationStatus(task.notification_status)}</td>
                <td>{formatShortDateTime(task.updated_at)}</td>
                <td>
                  {task.status === "pending" && (
                    <button onClick={() => onCancel(task)} type="button">取消</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </section>
  );
}
```

Import helper functions.

- [ ] **Step 4: Load and cancel tasks**

In lazy view effect, add:

```typescript
if (activeView === "automationTasks") {
  loadPaperAutomationTasks()
    .then(setPaperAutomationTasks)
    .then(markLazyViewLoaded)
    .catch(() => setAutomationError("读取自动任务失败"));
}
```

Render:

```tsx
{activeView === "automationTasks" && (
  <PaperAutomationTaskView
    tasks={paperAutomationTasks}
    onRefresh={() => {
      loadPaperAutomationTasks().then(setPaperAutomationTasks);
    }}
    onCancel={(task) => {
      cancelPaperAutomationTask(task.id)
        .then((updated) => {
          setPaperAutomationTasks((current) =>
            current.map((item) => (item.id === updated.id ? updated : item))
          );
        })
        .catch((error) => setAutomationError(formatActionError("取消自动任务失败", error)));
    }}
  />
)}
```

- [ ] **Step 5: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/pages/DashboardPage.tsx web/src/paperAutomationWorkspace.ts web/src/mockData.ts
git commit -m "Add paper automation task page"
```

## Task 11: Add Detail View For Task Results

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Add selected task state**

In `DashboardPage.tsx`:

```typescript
const [selectedAutomationTask, setSelectedAutomationTask] = useState<PaperAutomationTask | null>(null);
```

- [ ] **Step 2: Add detail button and panel**

In `PaperAutomationTaskView`, add prop:

```typescript
onOpenDetail: (task: PaperAutomationTask) => void;
```

Add button:

```tsx
<button onClick={() => onOpenDetail(task)} type="button">详情</button>
```

Add detail panel below table:

```tsx
{selectedTask && (
  <Panel title="任务详情">
    {selectedTask.error_message && <div className="inline-warning">{selectedTask.error_message}</div>}
    {selectedTask.notification_error && <div className="inline-warning">{selectedTask.notification_error}</div>}
    <pre className="json-preview">
      {JSON.stringify(selectedTask.result_payload ?? {}, null, 2)}
    </pre>
  </Panel>
)}
```

Use `selectedTask` prop passed from parent.

- [ ] **Step 3: Add CSS for JSON preview**

In `web/src/styles.css`:

```css
.json-preview {
  background: #0f172a;
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 12px;
  max-height: 420px;
  overflow: auto;
  padding: 12px;
  white-space: pre-wrap;
}
```

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add web/src/pages/DashboardPage.tsx web/src/styles.css
git commit -m "Add paper automation task detail view"
```

## Task 12: Final Verification

**Files:**
- No source edits unless failures are found.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\Python312\python.exe -m pytest tests/test_paper_automation_service.py tests/test_paper_automation_scheduler.py tests/test_web_console_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests/build**

Run:

```powershell
cd web
npm test -- --run
npm run build
```

Expected: PASS.

- [ ] **Step 3: Manual smoke with Web control script**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart
```

Open `http://127.0.0.1:5173`.

Smoke steps:

1. Open `比赛列表`.
2. Use a kickoff window that already has local matches.
3. Click `创建自动任务`.
4. Save a task with a future trigger time.
5. Open `自动任务`.
6. Confirm the task appears as `待执行`.
7. Cancel it and confirm it becomes `已取消`.

- [ ] **Step 4: Verify no secrets are committed**

Run:

```powershell
git diff --cached
git status --short
rg -n "BARK_PUSH_URL|api.day.app" . -g '!docs/superpowers/specs/2026-06-15-paper-automation-task-queue-design.md' -g '!docs/superpowers/plans/2026-06-15-paper-automation-task-queue.md'
```

Expected: no `.env` or real Bark URL is staged or committed.

- [ ] **Step 5: Final commit if verification fixes were needed**

If Task 12 required fixes:

```powershell
git add <fixed files>
git commit -m "Verify paper automation task queue"
```

If no fixes were needed, do not create an empty commit.
