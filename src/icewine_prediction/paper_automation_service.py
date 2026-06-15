from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.bark_notification_service import (
    BarkMessage,
    BarkPushResult,
    format_paper_automation_bark_messages,
    load_bark_push_url,
    push_bark_message,
)
from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.models import Match, PaperAutomationTask, PaperRecommendationRecord
from icewine_prediction.paper_confidence_service import (
    PaperConfidenceGroup,
    build_paper_confidence_workspace,
)
from icewine_prediction.paper_recommendation_queue_service import (
    PaperRecommendationQueueReport,
    PaperQueueScoreResult,
    build_paper_recommendation_queue,
)
from icewine_prediction.paper_recommendation_tracking_service import (
    create_paper_record_from_queue_row,
)


class PaperAutomationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PaperAutomationExecutionResult:
    status: str
    notification_status: str
    result_payload: dict[str, Any]


_DEFAULT_BARK_PUSH_URL = object()


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


def list_paper_automation_tasks(
    session: Session,
    *,
    limit: int = 100,
) -> list[PaperAutomationTask]:
    return (
        session.query(PaperAutomationTask)
        .order_by(PaperAutomationTask.trigger_at.desc(), PaperAutomationTask.id.desc())
        .limit(limit)
        .all()
    )


def build_paper_automation_task_payload(
    session: Session,
    task: PaperAutomationTask,
) -> dict[str, Any]:
    return {
        "id": task.id,
        "created_by": task.created_by,
        "created_at": _format_beijing_datetime(task.created_at),
        "updated_at": _format_beijing_datetime(task.updated_at),
        "trigger_at": _format_beijing_datetime(task.trigger_at),
        "match_window_start": _format_beijing_datetime(task.match_window_start),
        "match_window_end": _format_beijing_datetime(task.match_window_end),
        "started_at": _format_beijing_datetime(task.started_at),
        "finished_at": _format_beijing_datetime(task.finished_at),
        "missed_at": _format_beijing_datetime(task.missed_at),
        "cancelled_at": _format_beijing_datetime(task.cancelled_at),
        "status": task.status,
        "notification_status": task.notification_status,
        "notification_error": task.notification_error,
        "error_message": task.error_message,
        "target_match_count": count_matches_in_window(
            session,
            match_window_start=as_beijing_datetime(task.match_window_start),
            match_window_end=as_beijing_datetime(task.match_window_end),
        ),
        "result_payload": _parse_result_payload(task.result_payload),
    }


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

    while True:
        task = (
            session.query(PaperAutomationTask)
            .filter(PaperAutomationTask.status == "pending")
            .order_by(PaperAutomationTask.trigger_at.asc(), PaperAutomationTask.id.asc())
            .first()
        )
        if task is None or as_beijing_datetime(task.trigger_at) > now:
            return None
        if now <= as_beijing_datetime(task.trigger_at) + timedelta(minutes=grace_minutes):
            break
        task.status = "missed"
        task.missed_at = now
        task.updated_at = now
        session.commit()

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


def execute_paper_automation_task(
    session: Session,
    task_id: int,
    *,
    now: datetime,
    odds_syncer: Callable[[list[int]], Any],
    queue_builder: Callable[[Session, PaperAutomationTask], PaperRecommendationQueueReport],
    bark_push_url: str | None | object = _DEFAULT_BARK_PUSH_URL,
    bark_sender: Callable[[str, BarkMessage], BarkPushResult] = push_bark_message,
) -> PaperAutomationExecutionResult:
    now = as_beijing_datetime(now)
    task = session.get(PaperAutomationTask, task_id)
    if task is None:
        raise PaperAutomationValidationError(f"自动任务不存在: {task_id}")
    if task.status != "running":
        raise PaperAutomationValidationError("只能执行运行中的自动任务")

    try:
        target_match_ids = _target_match_ids(session, task)
        odds_sync_result = odds_syncer(target_match_ids)
        queue_report = queue_builder(session, task)
        created_record_ids, skipped_records = _record_queue_candidates(
            session,
            queue_report,
            recorded_at=now,
        )
        groups = _confidence_groups_for_records(session, created_record_ids)
        messages = format_paper_automation_bark_messages(
            groups=groups,
            recorded_count=len(created_record_ids),
            summary_lines=_execution_summary_lines(
                odds_sync_result=odds_sync_result,
                queue_report=queue_report,
                created_count=len(created_record_ids),
                skipped_count=len(skipped_records),
            ),
        )
        notification_status, notification_error = _send_bark_messages(
            messages,
            bark_push_url=(
                load_bark_push_url()
                if bark_push_url is _DEFAULT_BARK_PUSH_URL
                else bark_push_url
            ),
            bark_sender=bark_sender,
        )
        bark_payload = {
            "notification_status": notification_status,
            "notification_error": notification_error,
            "messages": [{"title": message.title, "body": message.body} for message in messages],
        }
        batch_record_payload = {
            "created_record_ids": created_record_ids,
            "created_count": len(created_record_ids),
            "skipped_count": len(skipped_records),
            "skipped": skipped_records,
        }
        result_payload = {
            "target_match_ids": target_match_ids,
            "odds": odds_sync_result,
            "odds_sync_result": odds_sync_result,
            "queue": {
                "total_matches": queue_report.total_matches,
                "candidate_count": queue_report.candidate_count,
                "status_counts": queue_report.status_counts,
                "discarded_by_robustness_match_count": getattr(
                    queue_report,
                    "discarded_by_robustness_match_count",
                    0,
                ),
            },
            "batch_record": batch_record_payload,
            "created_record_ids": created_record_ids,
            "confidence_group_keys": [group.group_key for group in groups],
            "bark": bark_payload,
            "bark_message_count": len(messages),
        }
        task.status = "success"
        task.notification_status = notification_status
        task.notification_error = notification_error
        task.error_message = None
        task.result_payload = json.dumps(result_payload, ensure_ascii=False, default=str)
        task.finished_at = now
        task.updated_at = now
        session.commit()
        return PaperAutomationExecutionResult(
            status=task.status,
            notification_status=task.notification_status,
            result_payload=result_payload,
        )
    except Exception as exc:
        session.rollback()
        task = session.get(PaperAutomationTask, task_id)
        if task is not None:
            task.status = "failed"
            task.error_message = f"{type(exc).__name__}: {exc}"
            task.finished_at = now
            task.updated_at = now
            session.commit()
        raise


def _execution_summary_lines(
    *,
    odds_sync_result: Any,
    queue_report: PaperRecommendationQueueReport,
    created_count: int,
    skipped_count: int,
) -> list[str]:
    return [
        _odds_summary_text(odds_sync_result),
        (
            f"候选{queue_report.candidate_count} "
            f"记录{created_count} 跳过{skipped_count}"
        ),
    ]


def _odds_summary_text(odds_sync_result: Any) -> str:
    if not isinstance(odds_sync_result, dict):
        return "赔率回填：结果已返回"
    success_count = _count_result_items(odds_sync_result, "success")
    failed_count = _count_result_items(odds_sync_result, "failed")
    skipped_count = _count_result_items(odds_sync_result, "skipped")
    if success_count == 0 and failed_count == 0 and skipped_count == 0:
        return "赔率回填：结果已返回"
    return f"赔率回填：成功{success_count} 失败{failed_count} 跳过{skipped_count}"


def _count_result_items(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, list | tuple | set):
        return len(value)
    if value is None:
        return 0
    return 1


def _format_beijing_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_beijing_datetime(value).isoformat()


def _parse_result_payload(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def build_real_paper_queue_for_task(
    session: Session,
    task: PaperAutomationTask,
    *,
    now: datetime,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult] | None = None,
    display_name_service: DisplayNameService | None = None,
) -> PaperRecommendationQueueReport:
    return build_paper_recommendation_queue(
        session,
        now=as_beijing_datetime(now),
        start_time=as_beijing_datetime(task.match_window_start),
        end_time=as_beijing_datetime(task.match_window_end),
        scorer=scorer,
        display_name_service=display_name_service,
    )


def _target_match_ids(session: Session, task: PaperAutomationTask) -> list[int]:
    rows = (
        session.query(Match.id)
        .filter(Match.kickoff_time >= as_beijing_datetime(task.match_window_start))
        .filter(Match.kickoff_time <= as_beijing_datetime(task.match_window_end))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )
    return [match_id for (match_id,) in rows]


def _record_queue_candidates(
    session: Session,
    queue_report: PaperRecommendationQueueReport,
    *,
    recorded_at: datetime,
) -> tuple[list[int], list[dict[str, Any]]]:
    created_record_ids: list[int] = []
    skipped: list[dict[str, Any]] = []
    for row in queue_report.rows:
        if row.status != "candidate":
            continue
        try:
            record = create_paper_record_from_queue_row(session, row, recorded_at=recorded_at)
        except ValueError as exc:
            skipped.append(
                {
                    "match_id": row.match_id,
                    "strategy_key": row.strategy_key,
                    "reason": str(exc),
                }
            )
            continue
        created_record_ids.append(record.id)
    return created_record_ids, skipped


def _confidence_groups_for_records(
    session: Session,
    record_ids: list[int],
) -> list[PaperConfidenceGroup]:
    if not record_ids:
        return []
    records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    workspace = build_paper_confidence_workspace(records)
    record_id_set = set(record_ids)
    return [
        group
        for group in workspace.groups
        if record_id_set.intersection(group.signal_record_ids)
    ]


def _send_bark_messages(
    messages: list[BarkMessage],
    *,
    bark_push_url: str | None,
    bark_sender: Callable[[str, BarkMessage], BarkPushResult],
) -> tuple[str, str | None]:
    if not bark_push_url:
        return "not_configured", None

    failures = []
    for message in messages:
        try:
            result = bark_sender(bark_push_url, message)
        except Exception as exc:
            result = BarkPushResult(success=False, error=f"{type(exc).__name__}: Bark sender failed")
        if not result.success:
            failures.append(_summarize_bark_failure(result, bark_push_url=bark_push_url))
    if failures:
        return "failed", "; ".join(failures)
    return "sent", None


def _summarize_bark_failure(result: BarkPushResult, *, bark_push_url: str) -> str:
    parts = []
    if result.status_code is not None:
        parts.append(f"status={result.status_code}")
    if result.response_text:
        parts.append(f"response={_safe_bark_detail(result.response_text, bark_push_url=bark_push_url)}")
    if result.error:
        parts.append(f"error={_safe_bark_detail(result.error, bark_push_url=bark_push_url)}")
    return ", ".join(parts) or "Bark push failed"


def _safe_bark_detail(value: str, *, bark_push_url: str) -> str:
    return _truncate(_redact_bark_secret(value, bark_push_url=bark_push_url), 200)


def _redact_bark_secret(value: str, *, bark_push_url: str) -> str:
    redacted = value.replace(bark_push_url, "[BARK_PUSH_URL]")
    parsed = urlparse(bark_push_url)
    secrets = {parsed.netloc}
    secrets.update(segment for segment in parsed.path.split("/") if segment)
    if parsed.query:
        secrets.add(parsed.query)
    if parsed.fragment:
        secrets.add(parsed.fragment)
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."
