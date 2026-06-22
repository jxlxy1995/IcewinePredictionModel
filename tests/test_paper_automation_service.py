from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import (
    League,
    Match,
    PaperAutomationTask,
    PaperRecommendationGroupSnapshot,
    Team,
)
import icewine_prediction.bark_notification_service as bark_notification_service
from icewine_prediction.bark_notification_service import (
    BarkMessage,
    BarkPushResult,
    format_paper_automation_bark_messages,
    load_bark_push_url,
    push_bark_message,
)
from icewine_prediction.paper_confidence_service import PaperConfidenceGroup
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueRow,
    PaperRecommendationQueueReport,
)
from icewine_prediction.paper_automation_service import (
    PaperAutomationValidationError,
    cancel_paper_automation_task,
    claim_due_paper_automation_task,
    create_paper_automation_task,
    execute_paper_automation_task,
)
from icewine_prediction.paper_strategy_registry import DEFAULT_STRATEGY
from icewine_prediction.paper_recommendation_tracking_service import (
    create_paper_record_from_queue_row,
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


def _seed_running_task(
    session,
    *,
    match_window_start: datetime,
    match_window_end: datetime,
    now: datetime,
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


def _queue_row(match: Match, *, status: str = "candidate") -> PaperQueueRow:
    return PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=match.kickoff_time.isoformat(),
        league_name=match.league.name,
        league_display_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        home_team_display_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        away_team_display_name=match.away_team.canonical_name,
        status=status,
        market_type=DEFAULT_STRATEGY.market_type,
        line=Decimal("-0.50"),
        side=DEFAULT_STRATEGY.side,
        recommended_handicap="Away +0.50",
        odds=Decimal("1.900"),
        model_probability=Decimal("0.8300"),
        market_probability=Decimal("0.5300"),
        edge=Decimal("0.3000"),
        line_bucket="away_underdog",
        risk_tags=("line_bucket:away_underdog",),
        scoring_edge=Decimal("0.3000"),
        strategy_key=DEFAULT_STRATEGY.strategy_key,
        strategy_display_name=DEFAULT_STRATEGY.display_name,
        signal_version=DEFAULT_STRATEGY.signal_version,
    )


def _queue_report(rows: list[PaperQueueRow]) -> PaperRecommendationQueueReport:
    return PaperRecommendationQueueReport(
        generated_at="2026-06-15T18:21:00+08:00",
        window_start="2026-06-15T18:30:00+08:00",
        window_end="2026-06-15T18:30:00+08:00",
        hours=0,
        near_start_hours=0,
        edge_threshold=Decimal("0.1000"),
        model_name="raw_hgb_team_form_plus_all_markets",
        total_matches=len({row.match_id for row in rows}),
        candidate_count=len([row for row in rows if row.status == "candidate"]),
        status_counts={
            status: len([row for row in rows if row.status == status])
            for status in {row.status for row in rows}
        },
        prefetch_requested=False,
        near_start_fixture_ids=[],
        prefetch_result=None,
        rows=rows,
    )


def _seed_automation_snapshot_task(session, *, now: datetime) -> PaperAutomationTask:
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
        source_match_id="fixture-automation-snapshot-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 22, 19, 0, tzinfo=BEIJING),
        status="scheduled",
        season=2026,
    )
    task = PaperAutomationTask(
        created_at=now,
        updated_at=now,
        created_by="web",
        trigger_at=now,
        match_window_start=match.kickoff_time,
        match_window_end=match.kickoff_time,
        status="running",
        notification_status="pending",
        started_at=now,
    )
    session.add_all([league, home, away, match, task])
    session.commit()
    return task


def _automation_snapshot_queue_report(session, task: PaperAutomationTask) -> PaperRecommendationQueueReport:
    match = (
        session.query(Match)
        .filter(Match.kickoff_time == task.match_window_start)
        .one()
    )
    row = PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=match.kickoff_time.isoformat(),
        league_name=match.league.name,
        league_display_name="日职联",
        home_team_name=match.home_team.canonical_name,
        home_team_display_name="横滨水手",
        away_team_name=match.away_team.canonical_name,
        away_team_display_name="神户胜利船",
        status="candidate",
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        side="away_cover",
        recommended_handicap="客队 +0.50",
        odds=Decimal("1.930"),
        model_probability=Decimal("0.5600"),
        market_probability=Decimal("0.5100"),
        edge=Decimal("0.1200"),
        line_bucket="away_underdog",
        risk_tags=("line_bucket:away_underdog",),
        scoring_edge=Decimal("0.1200"),
        strategy_key="asian_away_cover_hgb_edge_v1",
        strategy_display_name="亚盘客队方向 HGB edge v1",
        signal_version="v1",
    )
    return PaperRecommendationQueueReport(
        generated_at=task.started_at.isoformat(),
        window_start=task.match_window_start.isoformat(),
        window_end=task.match_window_end.isoformat(),
        hours=72,
        near_start_hours=6,
        edge_threshold=Decimal("0.10"),
        model_name="hgb",
        total_matches=1,
        candidate_count=1,
        status_counts={"candidate": 1},
        prefetch_requested=False,
        near_start_fixture_ids=[],
        prefetch_result=None,
        rows=[row],
    )


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
    assert "1. 18:30 日职联 横滨水手1 vs 神户胜利船1" in body
    assert "   客队 +0.50  评分80 推荐1.50手" in body
    assert "2. 18:30 日职联 横滨水手2 vs 神户胜利船2" in body
    assert "   客队 +0.50  评分92 推荐2.50手" in body
    assert "3. 20:00 日职联 横滨水手3 vs 神户胜利船3" in body
    assert "   客队 +0.50  评分61 推荐0.75手" in body


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
        assert combined_body.count(f"{index}. 18:30 日职联 横滨水手{index} vs 神户胜利船{index}") == 1


def test_format_bark_messages_splits_after_summary_without_exceeding_limit():
    groups = [_confidence_group(index) for index in range(1, 5)]

    messages = format_paper_automation_bark_messages(
        groups=groups,
        recorded_count=len(groups),
        summary_lines=["赔率回填：成功4 失败0 跳过0", "候选4 记录4 跳过0"],
        max_body_chars=130,
    )

    assert len(messages) > 1
    assert all(len(message.body) <= 130 for message in messages)
    assert all(message.body.startswith("赔率回填：成功4 失败0 跳过0\n候选4 记录4 跳过0") for message in messages)
    combined_body = "\n".join(message.body for message in messages)
    for index in range(1, 5):
        assert combined_body.count(f"{index}. 18:30 日职联 横滨水手{index} vs 神户胜利船{index}") == 1


def test_format_bark_messages_splits_oversized_summary_without_exceeding_limit():
    group = _confidence_group(1)

    messages = format_paper_automation_bark_messages(
        groups=[group],
        recorded_count=1,
        summary_lines=["摘要" * 20],
        max_body_chars=10,
    )

    assert len(messages) > 1
    assert all(len(message.body) <= 10 for message in messages)
    combined_body = "\n".join(message.body for message in messages)
    normalized_body = combined_body.replace("\n", "")
    assert "摘要摘要摘要" in combined_body
    assert "1. 18:30 日职联 横滨水手1 vs 神户胜利船1" in normalized_body


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


def test_execute_task_records_candidates_and_sends_bark_from_confidence_groups():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []
    odds_calls = []

    with _session() as session:
        match = _seed_match(session, kickoff)
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        def odds_syncer(match_ids):
            odds_calls.append(match_ids)
            return {"ok": match_ids}

        def queue_builder(session_arg, task_arg):
            assert session_arg is session
            assert task_arg.id == task.id
            return _queue_report([_queue_row(match)])

        def bark_sender(push_url, message):
            sent_messages.append((push_url, message))
            return BarkPushResult(success=True, status_code=200, response_text="ok")

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=odds_syncer,
            queue_builder=queue_builder,
            bark_push_url="https://example.com/bark/secret-token",
            bark_sender=bark_sender,
        )

        loaded = session.get(PaperAutomationTask, task.id)
        payload = json.loads(loaded.result_payload)

    assert odds_calls == [[match.id]]
    assert result.status == "success"
    assert result.notification_status == "sent"
    assert loaded.status == "success"
    assert loaded.notification_status == "sent"
    assert loaded.finished_at == now
    assert payload["created_record_ids"]
    assert payload["batch_record"]["created_record_ids"] == payload["created_record_ids"]
    assert payload["batch_record"]["skipped"] == []
    assert payload["bark"]["notification_status"] == "sent"
    assert payload["bark"]["messages"][0]["body"] == sent_messages[0][1].body
    assert sent_messages[0][0] == "https://example.com/bark/secret-token"
    assert "\u63a8\u83501.50\u624b" in sent_messages[0][1].body


def test_execute_task_creates_group_snapshots_and_payload_ids():
    now = datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING)

    with _session() as session:
        task = _seed_automation_snapshot_task(session, now=now)
        queue_report = _automation_snapshot_queue_report(session, task)

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"success": match_ids, "failed": []},
            queue_builder=lambda session, task: queue_report,
            bark_push_url=None,
        )

        snapshot_ids = result.result_payload["snapshot_ids"]
        assert snapshot_ids
        assert session.query(PaperRecommendationGroupSnapshot).count() == len(snapshot_ids)
        assert result.result_payload["confidence_group_keys"]


def test_execute_task_bark_title_uses_created_record_count():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []

    with _session() as session:
        first_match = _seed_match(session, kickoff)
        second_match = Match(
            source_name="api-football",
            source_match_id="fixture-second",
            league=first_match.league,
            home_team=first_match.home_team,
            away_team=first_match.away_team,
            kickoff_time=kickoff + timedelta(minutes=30),
            status="scheduled",
            season=2026,
        )
        session.add(second_match)
        session.commit()
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff + timedelta(minutes=30),
            now=now,
        )

        execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"ok": match_ids},
            queue_builder=lambda session_arg, task_arg: _queue_report(
                [_queue_row(first_match), _queue_row(second_match)]
            ),
            bark_push_url="https://example.com/bark/secret-token",
            bark_sender=lambda push_url, message: sent_messages.append(message)
            or BarkPushResult(success=True),
        )

    assert sent_messages[0].title == "纸面自动任务：已记录 2 条"


def test_execute_task_loads_default_bark_push_url_from_environment(monkeypatch):
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []
    monkeypatch.setenv("BARK_PUSH_URL", " https://example.com/bark/from-env ")

    with _session() as session:
        match = _seed_match(session, kickoff)
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"ok": match_ids},
            queue_builder=lambda session_arg, task_arg: _queue_report([_queue_row(match)]),
            bark_sender=lambda push_url, message: sent_messages.append((push_url, message))
            or BarkPushResult(success=True),
        )

    assert result.notification_status == "sent"
    assert sent_messages[0][0] == "https://example.com/bark/from-env"


def test_execute_task_continues_after_partial_odds_failure_and_sends_empty_notice():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []

    with _session() as session:
        match = _seed_match(session, kickoff)
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"failed": [{"match_id": match_ids[0], "error": "timeout"}]},
            queue_builder=lambda session_arg, task_arg: _queue_report([]),
            bark_push_url="https://example.com/bark/secret-token",
            bark_sender=lambda push_url, message: sent_messages.append(message)
            or BarkPushResult(success=True),
        )

        loaded = session.get(PaperAutomationTask, task.id)
        payload = json.loads(loaded.result_payload)

    assert result.status == "success"
    assert loaded.status == "success"
    assert loaded.notification_status == "sent"
    assert payload["target_match_ids"] == [match.id]
    assert payload["created_record_ids"] == []
    assert "赔率回填" in sent_messages[0].body
    assert "失败1" in sent_messages[0].body
    assert "\u6ca1\u6709\u8bb0\u5f55\u5230\u5019\u9009" in sent_messages[0].body


def test_execute_task_marks_bark_failure_without_failing_task():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)

    with _session() as session:
        match = _seed_match(session, kickoff)
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"ok": match_ids},
            queue_builder=lambda session_arg, task_arg: _queue_report([_queue_row(match)]),
            bark_push_url="https://example.com/bark/secret-token",
            bark_sender=lambda push_url, message: BarkPushResult(
                success=False,
                status_code=500,
                response_text=f"server error for {push_url}",
                error="token secret-token rejected",
            ),
        )

        loaded = session.get(PaperAutomationTask, task.id)
        payload = json.loads(loaded.result_payload)

    assert result.status == "success"
    assert loaded.status == "success"
    assert loaded.notification_status == "failed"
    assert "500" in loaded.notification_error
    assert "server error" in loaded.notification_error
    assert "example.com" not in loaded.notification_error
    assert "secret-token" not in loaded.notification_error
    assert payload["bark"]["notification_status"] == "failed"
    assert "example.com" not in payload["bark"]["notification_error"]
    assert "secret-token" not in payload["bark"]["notification_error"]


def test_execute_task_skips_duplicate_record_without_failing_task():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)

    with _session() as session:
        match = _seed_match(session, kickoff)
        row = _queue_row(match)
        create_paper_record_from_queue_row(session, row, recorded_at=now - timedelta(minutes=1))
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: {"ok": match_ids},
            queue_builder=lambda session_arg, task_arg: _queue_report([row]),
            bark_push_url=None,
        )

        loaded = session.get(PaperAutomationTask, task.id)
        payload = json.loads(loaded.result_payload)

    assert result.status == "success"
    assert loaded.status == "success"
    assert payload["batch_record"]["created_record_ids"] == []
    assert payload["batch_record"]["skipped_count"] == 1
    assert payload["batch_record"]["skipped"][0]["match_id"] == match.id
    assert "duplicate active paper recommendation record" in payload["batch_record"]["skipped"][0]["reason"]


def test_load_bark_push_url_reads_environment(monkeypatch):
    monkeypatch.setenv("BARK_PUSH_URL", " https://example.com/bark ")

    assert load_bark_push_url() == "https://example.com/bark"


def test_push_bark_message_retries_until_success(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        status_code = 500
        text = "server error"

    class SuccessResponse:
        status_code = 200
        text = "ok"

    def fake_post(push_url, *, json, timeout):
        calls.append((push_url, json, timeout))
        return SuccessResponse() if len(calls) == 3 else Response()

    monkeypatch.setattr(bark_notification_service.requests, "post", fake_post)
    monkeypatch.setattr(bark_notification_service.time, "sleep", sleeps.append)

    result = push_bark_message(
        "https://example.com/bark",
        BarkMessage(title="标题", body="正文"),
        timeout_seconds=3,
    )

    assert result == BarkPushResult(success=True, status_code=200, response_text="ok")
    assert calls == [
        ("https://example.com/bark", {"title": "标题", "body": "正文"}, 3),
        ("https://example.com/bark", {"title": "标题", "body": "正文"}, 3),
        ("https://example.com/bark", {"title": "标题", "body": "正文"}, 3),
    ]
    assert sleeps == [10.0, 10.0]


def test_push_bark_message_posts_json_and_preserves_failure_text(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        status_code = 500
        text = "server error"

    def fake_post(push_url, *, json, timeout):
        calls.append((push_url, json, timeout))
        return Response()

    monkeypatch.setattr(bark_notification_service.requests, "post", fake_post)
    monkeypatch.setattr(bark_notification_service.time, "sleep", sleeps.append)

    result = push_bark_message(
        "https://example.com/bark",
        BarkMessage(title="标题", body="正文"),
        timeout_seconds=3,
    )

    assert calls == [("https://example.com/bark", {"title": "标题", "body": "正文"}, 3)] * 5
    assert sleeps == [10.0, 10.0, 10.0, 10.0]
    assert result == BarkPushResult(success=False, status_code=500, response_text="server error")


def test_push_bark_message_redacts_secret_url_from_exception(monkeypatch):
    sleeps = []

    def fake_post(push_url, *, json, timeout):
        raise bark_notification_service.requests.RequestException(
            f"request failed for {push_url}"
        )

    monkeypatch.setattr(bark_notification_service.requests, "post", fake_post)
    monkeypatch.setattr(bark_notification_service.time, "sleep", sleeps.append)

    result = push_bark_message(
        "https://api.day.app/secret-token/纸面自动任务",
        BarkMessage(title="标题", body="正文"),
    )

    assert result.success is False
    assert result.error is not None
    assert "api.day.app" not in result.error
    assert "secret-token" not in result.error
    assert sleeps == [10.0, 10.0, 10.0, 10.0]


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
