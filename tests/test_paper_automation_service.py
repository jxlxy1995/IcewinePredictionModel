from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import League, Match, PaperAutomationTask, Team
from icewine_prediction.paper_automation_service import (
    PaperAutomationValidationError,
    cancel_paper_automation_task,
    claim_due_paper_automation_task,
    create_paper_automation_task,
)


BEIJING = ZoneInfo("Asia/Shanghai")


def _session():
    engine = create_memory_database()
    initialize_database(engine)
    return create_session_factory(engine)()


def _seed_match(session, kickoff: datetime) -> Match:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country_or_region="Japan",
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
        task_id = task.id

    with session_factory() as session:
        loaded = session.get(PaperAutomationTask, task_id)

    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.notification_status == "pending"


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


def test_create_task_rejects_duplicate_running_task():
    now = datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )
        task.status = "running"
        session.commit()

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


def test_claim_due_task_skips_missed_backlog_and_claims_next_due_task():
    now = datetime(2026, 6, 15, 18, 50, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 19, 0, tzinfo=BEIJING)
    created_at = datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING)
    with _session() as session:
        _seed_match(session, kickoff)
        overdue = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 0, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=created_at,
        )
        claimable = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 45, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=created_at,
        )

        claimed = claim_due_paper_automation_task(session, now=now, grace_minutes=20)

        assert claimed is not None
        assert claimed.id == claimable.id
        assert claimed.status == "running"
        assert session.get(type(overdue), overdue.id).status == "missed"
        assert session.get(type(overdue), overdue.id).missed_at == now


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


def test_cancel_pending_task_marks_cancelled_and_timestamps():
    now = datetime(2026, 6, 15, 18, 0, tzinfo=BEIJING)
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

        cancelled = cancel_paper_automation_task(session, task.id, now=now)

        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_at == now
        assert cancelled.updated_at == now
