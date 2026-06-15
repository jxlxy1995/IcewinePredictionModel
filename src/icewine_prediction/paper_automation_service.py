from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
        raise PaperAutomationValidationError("已存在重复的触发时间和比赛时间段待执行自动任务")
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
    running = session.query(PaperAutomationTask).filter(PaperAutomationTask.status == "running").first()
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
