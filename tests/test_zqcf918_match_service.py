from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import icewine_prediction.zqcf918_match_service as zqcf918_match_service
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.models import League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.odds_source_match_service import ExternalAliasInput
from icewine_prediction.zqcf918_match_service import (
    ZQCF918MatchIdUpdate,
    ZQCF918MatchDiscoverer,
    _match_candidates,
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


def test_sync_zqcf918_match_ids_loads_league_aliases_for_default_discoverer(
    session,
    tmp_path,
    monkeypatch,
):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(
            [
                "aliases:",
                "  - entity_type: league",
                "    source_name: zqcf918",
                "    canonical_name: Ekstraklasa (Poland)",
                "    alias_name: \u6ce2\u5170\u7532",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    captured = {}

    class CapturingDiscoverer:
        def __init__(self, *, league_aliases=None):
            captured["league_aliases"] = league_aliases

        def discover(self, matches):
            return {}

    monkeypatch.setattr(
        zqcf918_match_service,
        "ZQCF918MatchDiscoverer",
        CapturingDiscoverer,
    )
    match = _add_match(
        session,
        league_name="Ekstraklasa (Poland)",
        home_name="Wisla Plock",
        away_name="Widzew \u0141\u00f3d\u017a",
    )

    sync_zqcf918_match_ids_for_matches(session, [match])

    assert captured["league_aliases"] == [
        ExternalAliasInput("Ekstraklasa (Poland)", "\u6ce2\u5170\u7532")
    ]


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


class FakeIrishClient:
    def fetch_score_matches(self, type_id=1):
        return [
            {
                "ID": "4493692",
                "league": "爱甲",
                "home": "凯里FC",
                "away": "朗福德城",
                "time": "2026-06-27 02:45:00",
            },
            {
                "ID": "4493693",
                "league": "爱甲",
                "home": "都柏林大学",
                "away": "科布漫步者",
                "time": "2026-06-27 02:45:00",
            },
        ]


class FakeFinishedClient:
    def __init__(self):
        self.finished_dates = []

    def fetch_score_matches(self, type_id=1):
        return []

    def fetch_finished_score_matches(self, match_date):
        self.finished_dates.append(match_date)
        if match_date != "2026-06-26":
            return []
        return [
            {
                "ID": "4480129",
                "league": "\u51b0\u5c9b\u8d85",
                "home_en": "Breidablik",
                "away_en": "Vikingur Reykjavik",
                "time": "2026-06-26 03:15:00",
            }
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


def test_discoverer_allows_close_chinese_display_name_variants(session):
    first = _add_match(
        session,
        league_name="First Division Ireland",
        home_name="UCD",
        away_name="Cobh Ramblers",
        kickoff_time=datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
    )
    second = _add_match(
        session,
        league_name="First Division Ireland Second",
        home_name="Kerry",
        away_name="Longford Town",
        kickoff_time=datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
    )
    discoverer = ZQCF918MatchDiscoverer(
        client=FakeIrishClient(),
        display_names=DisplayNames(
            leagues={
                "First Division Ireland": "爱甲",
                "First Division Ireland Second": "爱甲",
            },
            teams={
                "UCD": "都柏林大学",
                "Cobh Ramblers": "科布漫游者",
                "Kerry": "凯里FC",
                "Longford Town": "郎福德城",
            },
        ),
    )

    discovered = discoverer.discover([first, second])

    assert discovered == {first.id: "4493693", second.id: "4493692"}


def test_discoverer_checks_finished_score_list_by_match_date(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild (Iceland)",
        home_name="Breidablik",
        away_name="Vikingur Reykjavik",
        kickoff_time=datetime(2026, 6, 25, 19, 15, tzinfo=ZoneInfo("UTC")),
    )
    client = FakeFinishedClient()
    discoverer = ZQCF918MatchDiscoverer(
        client=client,
        display_names=DisplayNames(
            leagues={"Urvalsdeild (Iceland)": "\u51b0\u5c9b\u8d85"},
            teams={
                "Breidablik": "\u8d1d\u96f7\u8fbe\u6bd4\u5386\u514b",
                "Vikingur Reykjavik": "\u7ef4\u4eac\u53e4",
            },
        ),
    )

    discovered = discoverer.discover([match])

    assert client.finished_dates == ["2026-06-26"]
    assert discovered == {match.id: "4480129"}


def test_match_candidates_uses_zqcf918_league_alias_without_changing_display_name(session):
    match = _add_match(
        session,
        league_name="Ekstraklasa (Poland)",
        home_name="Wisla Plock",
        away_name="Widzew \u0141\u00f3d\u017a",
        kickoff_time=datetime(2026, 8, 1, 0, 0),
    )
    candidate = {
        "ID": "4559263",
        "league": "\u6ce2\u5170\u7532",
        "home": "\u534e\u6c99\u666e\u6d1b\u514b",
        "away": "\u7ef4\u5fb7\u7956\u7f57\u5179",
        "time": "2026-08-01 00:00:00",
    }
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Ekstraklasa (Poland)": "\u6ce2\u5170\u8d85"},
            teams={
                "Wisla Plock": "\u534e\u6c99\u666e\u6d1b\u514b",
                "Widzew \u0141\u00f3d\u017a": "\u7ef4\u5fb7\u7956\u7f57\u5179",
            },
        )
    )

    assert display_service.display_league(match.league.name) == "\u6ce2\u5170\u8d85"
    assert _match_candidates(
        [match],
        [candidate],
        display_service=display_service,
    ) == {}
    assert _match_candidates(
        [match],
        [candidate],
        display_service=display_service,
        league_aliases=[
            ExternalAliasInput("Ekstraklasa (Poland)", "\u6ce2\u5170\u7532")
        ],
    ) == {match.id: "4559263"}


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
