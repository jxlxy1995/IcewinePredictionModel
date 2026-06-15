from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import League, Match, PaperAutomationTask, Team
import icewine_prediction.bark_notification_service as bark_notification_service
from icewine_prediction.bark_notification_service import (
    BarkMessage,
    BarkPushResult,
    format_paper_automation_bark_messages,
    load_bark_push_url,
    push_bark_message,
)
from icewine_prediction.paper_confidence_service import PaperConfidenceGroup
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


def _confidence_group(
    index: int,
    *,
    kickoff: datetime | None = None,
    confidence_score: int = 80,
    suggested_stake_units: Decimal = Decimal("1.50"),
    league_display_name: str | None = "日职联",
    home_team_display_name: str | None = None,
    away_team_display_name: str | None = None,
) -> PaperConfidenceGroup:
    return PaperConfidenceGroup(
        group_key=f"group-{index}",
        match_id=index,
        source_match_id=f"fixture-{index}",
        kickoff_time=kickoff or datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
        league_name="J1 League",
        league_display_name=league_display_name,
        home_team_name=f"Home {index}",
        home_team_display_name=home_team_display_name or f"横滨水手{index}",
        home_team_logo_url=None,
        home_score=None,
        away_team_name=f"Away {index}",
        away_team_display_name=away_team_display_name or f"神户胜利船{index}",
        away_team_logo_url=None,
        away_score=None,
        market_type="asian_handicap",
        logical_side="away",
        recommendation_text="客队 +0.50",
        representative_record_id=index,
        representative_strategy_key="asian_away_cover_hgb_edge_v1",
        representative_market_line=Decimal("0.50"),
        representative_odds=Decimal("1.900"),
        signal_record_ids=(index,),
        triggered_strategy_keys=("asian_away_cover_hgb_edge_v1",),
        triggered_strategy_display_names=("客队亚盘覆盖",),
        signal_families=("asian_away_hgb",),
        confidence_score=confidence_score,
        suggested_stake_units=suggested_stake_units,
        stake_cap_reason="none",
        status="pending",
        settlement_result=None,
        flat_profit_units=Decimal("0.000"),
        weighted_profit_units=Decimal("0.000"),
        warning=None,
    )


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


def test_format_bark_messages_includes_all_confidence_groups():
    groups = [
        _confidence_group(1, confidence_score=80, suggested_stake_units=Decimal("1.50")),
        _confidence_group(2, confidence_score=92, suggested_stake_units=Decimal("2.50")),
        _confidence_group(
            3,
            kickoff=datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC")),
            confidence_score=61,
            suggested_stake_units=Decimal("0.75"),
        ),
    ]

    messages = format_paper_automation_bark_messages(groups=groups, recorded_count=len(groups))

    assert len(messages) == 1
    assert messages[0].title == "纸面自动任务：已记录 3 条"
    body = messages[0].body
    assert "1. 日职联 横滨水手1 vs 神户胜利船1" in body
    assert "18:30 客队 +0.50  评分80 推荐1.50手" in body
    assert "2. 日职联 横滨水手2 vs 神户胜利船2" in body
    assert "18:30 客队 +0.50  评分92 推荐2.50手" in body
    assert "3. 日职联 横滨水手3 vs 神户胜利船3" in body
    assert "20:00 客队 +0.50  评分61 推荐0.75手" in body


def test_format_bark_messages_splits_without_dropping_groups():
    groups = [_confidence_group(index) for index in range(1, 8)]

    messages = format_paper_automation_bark_messages(
        groups=groups,
        recorded_count=len(groups),
        max_body_chars=130,
    )

    assert len(messages) > 1
    assert [message.title for message in messages] == [
        f"纸面自动任务：已记录 7 条（{index}/{len(messages)}）"
        for index in range(1, len(messages) + 1)
    ]
    combined_body = "\n".join(message.body for message in messages)
    for index in range(1, 8):
        assert combined_body.count(f"{index}. 日职联 横滨水手{index} vs 神户胜利船{index}") == 1


def test_format_bark_messages_splits_oversized_group_without_dropping_text():
    group = _confidence_group(
        1,
        league_display_name="超长联赛名称" * 5,
        home_team_display_name="超长主队名称" * 8,
        away_team_display_name="超长客队名称" * 8,
    )
    expected_body = format_paper_automation_bark_messages(groups=[group])[0].body

    messages = format_paper_automation_bark_messages(
        groups=[group],
        max_body_chars=30,
    )

    assert len(messages) > 1
    assert "".join(message.body for message in messages) == expected_body
    assert all(len(message.body) <= 30 for message in messages)


def test_format_bark_messages_returns_empty_candidate_notice():
    messages = format_paper_automation_bark_messages(groups=[], recorded_count=0)

    assert messages == [BarkMessage(title="纸面自动任务：已记录 0 条", body="没有记录到候选")]


def test_load_bark_push_url_reads_environment(monkeypatch):
    monkeypatch.setenv("BARK_PUSH_URL", " https://example.com/bark ")

    assert load_bark_push_url() == "https://example.com/bark"


def test_push_bark_message_posts_json_and_preserves_failure_text(monkeypatch):
    calls = []

    class Response:
        status_code = 500
        text = "server error"

    def fake_post(push_url, *, json, timeout):
        calls.append((push_url, json, timeout))
        return Response()

    monkeypatch.setattr(bark_notification_service.requests, "post", fake_post)

    result = push_bark_message(
        "https://example.com/bark",
        BarkMessage(title="标题", body="正文"),
        timeout_seconds=3,
    )

    assert calls == [("https://example.com/bark", {"title": "标题", "body": "正文"}, 3)]
    assert result == BarkPushResult(success=False, status_code=500, response_text="server error")


def test_push_bark_message_redacts_secret_url_from_exception(monkeypatch):
    def fake_post(push_url, *, json, timeout):
        raise bark_notification_service.requests.RequestException(
            f"request failed for {push_url}"
        )

    monkeypatch.setattr(bark_notification_service.requests, "post", fake_post)

    result = push_bark_message(
        "https://api.day.app/secret-token/纸面自动任务",
        BarkMessage(title="标题", body="正文"),
    )

    assert result.success is False
    assert result.error is not None
    assert "api.day.app" not in result.error
    assert "secret-token" not in result.error


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
