from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.zqcf918_match_service import (
    ZQCF918MatchIdUpdate,
    get_zqcf918_match_id,
    upsert_zqcf918_match_id,
)


def test_upsert_zqcf918_match_id_creates_manual_mapping(session):
    match = _add_match(session)

    result = upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=match.id, source_fixture_id="4460916", reason="manual:web-detail"),
    )

    assert result.source_fixture_id == "4460916"
    assert result.source_name == ZQCF918_SOURCE_NAME
    assert result.match_confidence == Decimal("1.0000")
    assert get_zqcf918_match_id(session, match.id).source_fixture_id == "4460916"


def test_upsert_zqcf918_match_id_updates_existing_mapping(session):
    match = _add_match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id="old",
            matched_at=datetime(2026, 6, 26, tzinfo=ZoneInfo("UTC")),
            match_confidence=Decimal("0.5000"),
            match_reason="auto",
        )
    )
    session.commit()

    upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=match.id, source_fixture_id="4460916", reason="manual:web-detail"),
    )

    rows = session.query(OddsSourceMatch).filter_by(match_id=match.id, source_name=ZQCF918_SOURCE_NAME).all()
    assert len(rows) == 1
    assert rows[0].source_fixture_id == "4460916"
    assert rows[0].match_reason == "manual:web-detail"


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
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match
