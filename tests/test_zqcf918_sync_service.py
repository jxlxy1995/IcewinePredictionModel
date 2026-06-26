from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import PINNACLE_BOOKMAKER, ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918TimelinePayload
from icewine_prediction.zqcf918_sync_service import run_zqcf918_sync_for_session


class FakeZQCF918Client:
    def __init__(self):
        self.calls = []

    def fetch_all_timelines(self, match_id):
        self.calls.append(match_id)
        return [
            ZQCF918TimelinePayload(
                market="asian_handicap",
                rows=[{"c": "1.91", "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
            ZQCF918TimelinePayload(
                market="total_goals",
                rows=[{"c": "1.88", "d": "2.5", "e": "2.02", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
            ZQCF918TimelinePayload(
                market="match_winner",
                rows=[{"c1": "2.40", "c2": "3.20", "c3": "2.90", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
        ]


def test_run_zqcf918_sync_stores_pinnacle_snapshots(session):
    match = _add_match(session)
    _add_source_match(session, match.id, "4460916")
    client = FakeZQCF918Client()

    result = run_zqcf918_sync_for_session(session=session, match_ids=[match.id], client=client)

    assert client.calls == ["4460916"]
    assert [item["match_id"] for item in result["success"]] == [match.id]
    assert result["failed"] == []
    assert result["requests"] == 3
    assert result["credits"] == 0
    snapshots = session.query(HistoricalOddsSnapshot).filter_by(match_id=match.id).all()
    assert len(snapshots) == 7
    assert {row.source_name for row in snapshots} == {ZQCF918_SOURCE_NAME}
    assert {row.bookmaker for row in snapshots} == {PINNACLE_BOOKMAKER}


def test_run_zqcf918_sync_skips_missing_match_id(session):
    match = _add_match(session)

    result = run_zqcf918_sync_for_session(session=session, match_ids=[match.id], client=FakeZQCF918Client())

    assert result["success"] == []
    assert [item["match_id"] for item in result["skipped"]] == [match.id]


def _add_match(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Home")
    away = Team(canonical_name="Away")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match


def _add_source_match(session, match_id, source_fixture_id):
    session.add(
        OddsSourceMatch(
            match_id=match_id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id=source_fixture_id,
            matched_at=datetime(2026, 6, 26, tzinfo=ZoneInfo("UTC")),
            match_confidence=Decimal("1.0000"),
            match_reason="manual",
        )
    )
    session.commit()
