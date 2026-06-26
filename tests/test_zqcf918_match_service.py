from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.display_service import DisplayNames
from icewine_prediction.models import League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.zqcf918_match_service import (
    ZQCF918MatchIdUpdate,
    ZQCF918MatchDiscoverer,
    get_zqcf918_match_id,
    sync_zqcf918_match_ids_for_matches,
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


class FakeDiscoverer:
    def __init__(self):
        self.calls = []

    def discover(self, matches):
        self.calls.append([match.id for match in matches])
        return {matches[0].id: "4460916"}


def test_sync_zqcf918_match_ids_only_targets_missing_mappings(session):
    first = _add_match(session, league_name="J1 League", home_name="Home One", away_name="Away One")
    second = _add_match(session, league_name="J2 League", home_name="Home Two", away_name="Away Two")
    upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=second.id, source_fixture_id="999", reason="manual:web-detail"),
    )
    discoverer = FakeDiscoverer()

    result = sync_zqcf918_match_ids_for_matches(session, [first, second], discoverer=discoverer)

    assert discoverer.calls == [[first.id]]
    assert [item["match_id"] for item in result["success"]] == [first.id]
    assert [item["match_id"] for item in result["skipped"]] == [second.id]
    assert get_zqcf918_match_id(session, first.id).source_fixture_id == "4460916"


class FakeClient:
    def fetch_score_matches(self, type_id=1):
        return [
            {
                "ID": "4477378",
                "league": "芬甲",
                "home": "克鲁比04",
                "away": "SJK学院",
                "time": "2026-06-27 00:00:00",
            },
            {
                "ID": "4477379",
                "league": "芬甲",
                "home": "PK35万塔",
                "away": "MP米可力",
                "time": "2026-06-27 00:00:00",
            },
        ]


def test_discoverer_matches_by_chinese_display_names(session):
    first = _add_match(
        session,
        league_name="Ykkosliiga Finland",
        home_name="Klubi-04",
        away_name="SJK Akatemia",
        kickoff_time=datetime(2026, 6, 26, 16, 0, tzinfo=ZoneInfo("UTC")),
    )
    second = _add_match(
        session,
        league_name="Ykkosliiga Finland Second",
        home_name="PK-35",
        away_name="MP",
        kickoff_time=datetime(2026, 6, 26, 16, 0, tzinfo=ZoneInfo("UTC")),
    )
    discoverer = ZQCF918MatchDiscoverer(
        client=FakeClient(),
        display_names=DisplayNames(
            leagues={
                "Ykkosliiga Finland": "芬甲",
                "Ykkosliiga Finland Second": "芬甲",
            },
            teams={
                "Klubi-04": "克鲁比04",
                "SJK Akatemia": "SJK学院",
                "PK-35": "PK35万塔",
                "MP": "MP米可力",
            },
        ),
    )

    discovered = discoverer.discover([first, second])

    assert discovered == {first.id: "4477378", second.id: "4477379"}


def _add_match(
    session,
    *,
    league_name: str = "J1 League",
    home_name: str = "Home",
    away_name: str = "Away",
    kickoff_time: datetime | None = None,
):
    league = League(name=league_name, country_or_region="Japan", level=1)
    home = Team(canonical_name=home_name)
    away = Team(canonical_name=away_name)
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time or datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match
