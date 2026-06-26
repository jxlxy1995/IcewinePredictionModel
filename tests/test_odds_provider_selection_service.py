from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    PINNACLE_BOOKMAKER,
    SBOBET_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    filter_priority_trusted_snapshots,
    filter_priority_pinnacle_snapshots,
    source_label_for_snapshots,
    TRUSTED_SNAPSHOT_PRIORITY,
    ZQCF918_SOURCE_NAME,
)


def test_filter_priority_pinnacle_snapshots_prefers_the_odds_api_per_match():
    old = _snapshot(match_id=1, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))
    new = _snapshot(match_id=1, source_name=THE_ODDS_API_SOURCE_NAME, odds=Decimal("1.95"))
    ignored = _snapshot(
        match_id=1,
        source_name=THE_ODDS_API_SOURCE_NAME,
        odds=Decimal("1.88"),
        bookmaker="bet365",
    )

    selected = filter_priority_pinnacle_snapshots([old, new, ignored])

    assert selected == [new]
    assert source_label_for_snapshots(selected) == "the_odds_api_pinnacle_historical"


def test_filter_priority_pinnacle_snapshots_falls_back_to_oddspapi():
    old = _snapshot(match_id=2, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))

    selected = filter_priority_pinnacle_snapshots([old])

    assert selected == [old]
    assert source_label_for_snapshots(selected) == "oddspapi_pinnacle_historical"


def test_filter_priority_pinnacle_snapshots_keeps_each_match_independent():
    match_one_old = _snapshot(match_id=1, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))
    match_one_new = _snapshot(match_id=1, source_name=THE_ODDS_API_SOURCE_NAME, odds=Decimal("1.95"))
    match_two_old = _snapshot(match_id=2, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("2.05"))

    selected = filter_priority_pinnacle_snapshots([match_one_old, match_one_new, match_two_old])

    assert selected == [match_one_new, match_two_old]


def test_filter_priority_trusted_snapshots_falls_back_to_sbobet_when_pinnacle_missing():
    sbobet = _snapshot(
        match_id=3,
        source_name=ODDSPAPI_SOURCE_NAME,
        bookmaker=SBOBET_BOOKMAKER,
        odds=Decimal("1.92"),
    )

    selected = filter_priority_trusted_snapshots([sbobet])

    assert selected == [sbobet]
    assert source_label_for_snapshots(selected) == "oddspapi_sbobet_historical"


def test_filter_priority_trusted_snapshots_prefers_pinnacle_over_sbobet_for_same_match():
    sbobet = _snapshot(
        match_id=4,
        source_name=ODDSPAPI_SOURCE_NAME,
        bookmaker=SBOBET_BOOKMAKER,
        odds=Decimal("1.92"),
    )
    pinnacle = _snapshot(
        match_id=4,
        source_name=THE_ODDS_API_SOURCE_NAME,
        bookmaker=PINNACLE_BOOKMAKER,
        odds=Decimal("1.95"),
    )

    selected = filter_priority_trusted_snapshots([sbobet, pinnacle])

    assert selected == [pinnacle]
    assert source_label_for_snapshots(selected) == "the_odds_api_pinnacle_historical"


def test_trusted_snapshot_priority_places_zqcf918_before_sbobet():
    assert TRUSTED_SNAPSHOT_PRIORITY == (
        (THE_ODDS_API_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ODDSPAPI_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER),
    )


def test_filter_priority_trusted_snapshots_prefers_zqcf918_over_sbobet_for_same_match():
    sbobet = _snapshot(
        match_id=5,
        source_name=ODDSPAPI_SOURCE_NAME,
        bookmaker=SBOBET_BOOKMAKER,
        odds=Decimal("1.92"),
    )
    zqcf918 = _snapshot(
        match_id=5,
        source_name=ZQCF918_SOURCE_NAME,
        bookmaker=PINNACLE_BOOKMAKER,
        odds=Decimal("1.94"),
    )

    selected = filter_priority_trusted_snapshots([sbobet, zqcf918])

    assert selected == [zqcf918]
    assert source_label_for_snapshots(selected) == "zqcf918_pinnacle_historical"


def _snapshot(
    *,
    match_id: int,
    source_name: str,
    odds: Decimal,
    bookmaker: str = PINNACLE_BOOKMAKER,
) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-{match_id}",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"{source_name}-ah",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 6, 25, 12, 0, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )
