import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.display_service import DisplayNames, DisplayNameService
from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.oddspapi_backfill_audit_service import (
    build_oddspapi_backfill_audit_for_session,
    format_oddspapi_backfill_audit_report,
)


def _match(session, league, home_name, away_name, source_match_id):
    home_team = Team(canonical_name=home_name)
    away_team = Team(canonical_name=away_name)
    session.add_all([home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 4, 20, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        home_score=1,
        away_score=0,
        source_name="api_football",
        source_match_id=source_match_id,
    )
    session.add(match)
    session.flush()
    return match


def test_backfill_audit_summarizes_worker_progress_with_display_league_name(
    session,
    tmp_path,
):
    league = League(
        name="Ligue 2",
        country_or_region="France",
        level=2,
        source_name="api_football",
        source_league_id="62",
        priority=90,
    )
    session.add(league)
    session.flush()
    successful_match = _match(session, league, "Paris FC", "Caen", "ligue2-success")
    unavailable_match = _match(session, league, "Nancy", "Laval", "ligue2-unavailable")
    unmatched_match = _match(session, league, "Rodez", "Bastia", "ligue2-unmatched")
    session.add_all(
        [
            OddsSourceMatch(
                match_id=successful_match.id,
                source_name="oddspapi",
                source_fixture_id="fixture-success",
                matched_at=datetime(2026, 5, 27, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="league/time/team match",
                historical_odds_status="success",
            ),
            OddsSourceMatch(
                match_id=unavailable_match.id,
                source_name="oddspapi",
                source_fixture_id="",
                matched_at=datetime(2026, 5, 27, 9, 1, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("0.0000"),
                match_reason="status=404",
                historical_odds_status="unavailable",
                historical_odds_error="status=404 fixture unavailable",
            ),
            OddsSourceMatch(
                match_id=unmatched_match.id,
                source_name="oddspapi",
                source_fixture_id="",
                matched_at=datetime(2026, 5, 27, 9, 2, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("0.0000"),
                match_reason="team mismatch",
                historical_odds_status="unmatched",
                historical_odds_error="team mismatch",
            ),
            HistoricalOddsSnapshot(
                match_id=successful_match.id,
                source_name="oddspapi",
                source_fixture_id="fixture-success",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="1070",
                market_name="Asian Handicap",
                market_line=Decimal("-0.25"),
                outcome_side="home",
                odds=Decimal("1.910"),
                snapshot_time=datetime(2026, 4, 19, 20, 0, tzinfo=ZoneInfo("UTC")),
                period="fulltime",
            ),
            HistoricalOddsSnapshot(
                match_id=successful_match.id,
                source_name="oddspapi",
                source_fixture_id="fixture-success",
                bookmaker="pinnacle",
                market_type="total_goals",
                market_id="10170",
                market_name="Over Under Full Time",
                market_line=Decimal("2.50"),
                outcome_side="over",
                odds=Decimal("1.880"),
                snapshot_time=datetime(2026, 4, 19, 20, 5, tzinfo=ZoneInfo("UTC")),
                period="fulltime",
            ),
        ]
    )
    session.commit()
    (tmp_path / "oddspapi-worker-progress.json").write_text(
        json.dumps(
            {
                "status": "running",
                "mode": "safe",
                "season": 2025,
                "worker_count": 1,
                "league_count": 1,
                "updated_at": "2026-05-27T09:30:00+08:00",
                "current_league": {
                    "league_id": "62",
                    "league_name": "Ligue 2",
                    "round": 3,
                    "processed_matches": 8,
                    "inserted_snapshots": 720,
                    "failed_matches": 1,
                    "requests_used": 24,
                },
                "totals": {
                    "processed_matches": 8,
                    "inserted_snapshots": 720,
                    "failed_matches": 1,
                    "requests_used": 24,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    display_service = DisplayNameService(
        DisplayNames(leagues={"Ligue 2": "法乙"}, teams={})
    )

    report = build_oddspapi_backfill_audit_for_session(
        session=session,
        season=2025,
        log_dir=tmp_path,
        display_service=display_service,
    )
    output = format_oddspapi_backfill_audit_report(report)

    assert report.worker_progress is not None
    assert report.worker_progress.current_league_display_name == "法乙"
    assert "当前 法乙 (Ligue 2) id=62 round=3 processed=8 snapshots=720 failed=1 requests=24" in output
    assert "法乙 (Ligue 2) id=62 finished=3 matched=1 snapshot_matches=1 snapshots=2" in output
    assert "status success=1 unavailable=1 unmatched=1" in output
    assert "status=404 fixture unavailable x1" in output
