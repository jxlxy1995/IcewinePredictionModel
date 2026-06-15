from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import League, Match, PaperAutomationTask, Team
from icewine_prediction.paper_automation_scheduler import (
    PaperAutomationScheduler,
    poll_paper_automation_once,
)
from icewine_prediction.paper_automation_service import create_paper_automation_task


BEIJING = ZoneInfo("Asia/Shanghai")


class TrackingSession:
    def __init__(self, session):
        self._session = session
        self.closed = False

    def __getattr__(self, name):
        return getattr(self._session, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        self.closed = True
        self._session.close()


def _session_factory():
    engine = create_memory_database()
    initialize_database(engine)
    return create_session_factory(engine)


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
        source_match_id=f"fixture-{kickoff.isoformat()}",
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


def _seed_running_task(
    session,
    *,
    now: datetime,
    match_window_start: datetime,
    match_window_end: datetime,
) -> PaperAutomationTask:
    task = PaperAutomationTask(
        created_at=now - timedelta(minutes=5),
        updated_at=now,
        created_by="test",
        trigger_at=now,
        match_window_start=match_window_start,
        match_window_end=match_window_end,
        status="running",
        notification_status="pending",
        started_at=now,
    )
    session.add(task)
    session.commit()
    return task


def test_poll_runs_one_due_task_and_keeps_serial_execution():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    base_factory = _session_factory()
    tracking_sessions: list[TrackingSession] = []

    with base_factory() as session:
        _seed_match(session, kickoff)
        first = create_paper_automation_task(
            session,
            trigger_at=now,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )
        second = create_paper_automation_task(
            session,
            trigger_at=now + timedelta(minutes=1),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

    def tracking_factory():
        session = TrackingSession(base_factory())
        tracking_sessions.append(session)
        return session

    executor_calls = []

    def executor(task_id: int):
        executor_calls.append(task_id)
        assert tracking_sessions[-1].closed
        with base_factory() as session:
            assert session.get(PaperAutomationTask, first.id).status == "running"
            assert session.get(PaperAutomationTask, second.id).status == "pending"

    claimed_id = poll_paper_automation_once(
        tracking_factory,
        now=now,
        grace_minutes=20,
        executor=executor,
    )

    assert claimed_id == first.id
    assert executor_calls == [first.id]
    with base_factory() as session:
        assert session.get(PaperAutomationTask, first.id).status == "running"
        assert session.get(PaperAutomationTask, second.id).status == "pending"


def test_poll_marks_overdue_task_missed():
    now = datetime(2026, 6, 15, 18, 50, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 19, 0, tzinfo=BEIJING)
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_match(session, kickoff)
        task = create_paper_automation_task(
            session,
            trigger_at=datetime(2026, 6, 15, 18, 0, tzinfo=BEIJING),
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
        )

    executor_calls = []
    claimed_id = poll_paper_automation_once(
        session_factory,
        now=now,
        grace_minutes=20,
        executor=executor_calls.append,
    )

    assert claimed_id is None
    assert executor_calls == []
    with session_factory() as session:
        loaded = session.get(PaperAutomationTask, task.id)
        assert loaded.status == "missed"
        assert loaded.missed_at == now.replace(tzinfo=None)


def test_poll_does_not_claim_when_running_task_exists():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    session_factory = _session_factory()
    with session_factory() as session:
        _seed_match(session, kickoff)
        running = _seed_running_task(
            session,
            now=now,
            match_window_start=kickoff,
            match_window_end=kickoff,
        )
        pending = PaperAutomationTask(
            created_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            updated_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            created_by="test",
            trigger_at=now,
            match_window_start=kickoff,
            match_window_end=kickoff,
            status="pending",
            notification_status="pending",
        )
        session.add(pending)
        session.commit()

    executor_calls = []
    claimed_id = poll_paper_automation_once(
        session_factory,
        now=now,
        grace_minutes=20,
        executor=executor_calls.append,
    )

    assert claimed_id is None
    assert executor_calls == []
    with session_factory() as session:
        assert session.get(PaperAutomationTask, running.id).status == "running"
        assert session.get(PaperAutomationTask, pending.id).status == "pending"


def test_scheduler_start_is_idempotent_and_stop_returns(monkeypatch):
    calls = []

    def fake_poll(session_factory, *, now, grace_minutes, executor):
        calls.append((now, grace_minutes))
        if len(calls) == 1:
            raise RuntimeError("transient scheduler failure")

    scheduler = PaperAutomationScheduler(
        session_factory=lambda: None,
        executor=lambda task_id: None,
        grace_minutes=7,
        poll_seconds=0.01,
        clock=lambda: datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
    )
    monkeypatch.setattr(
        "icewine_prediction.paper_automation_scheduler.poll_paper_automation_once",
        fake_poll,
    )

    scheduler.start()
    first_thread = scheduler._thread
    scheduler.start()
    time.sleep(0.05)
    scheduler.stop()

    assert first_thread is not None
    assert scheduler._thread is first_thread
    assert not first_thread.is_alive()
    assert len(calls) >= 2
