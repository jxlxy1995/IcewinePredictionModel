from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.odds_provider_selection_service import PINNACLE_BOOKMAKER, ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918TimelinePayload
from icewine_prediction.sources.zqcf918_odds_mapper import map_zqcf918_timelines


def test_maps_asian_total_and_match_winner_rows():
    payloads = [
        ZQCF918TimelinePayload(
            market="asian_handicap",
            rows=[{"c": "1.91", "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:00:00Z"}],
            raw_payload={},
        ),
        ZQCF918TimelinePayload(
            market="total_goals",
            rows=[{"c": "1.88", "d": "2.5", "e": "2.02", "changeTime": "2026-06-26T10:05:00Z"}],
            raw_payload={},
        ),
        ZQCF918TimelinePayload(
            market="match_winner",
            rows=[{"c1": "2.40", "c2": "3.20", "c3": "2.90", "changeTime": "2026-06-26T10:10:00Z"}],
            raw_payload={},
        ),
    ]

    snapshots = map_zqcf918_timelines(match_id=123, source_fixture_id="4460916", payloads=payloads)

    assert len(snapshots) == 7
    assert {(row.market_type, row.outcome_side) for row in snapshots} == {
        ("asian_handicap", "home"),
        ("asian_handicap", "away"),
        ("total_goals", "over"),
        ("total_goals", "under"),
        ("match_winner", "home"),
        ("match_winner", "draw"),
        ("match_winner", "away"),
    }
    asian_home = next(
        row for row in snapshots if row.market_type == "asian_handicap" and row.outcome_side == "home"
    )
    assert asian_home.source_name == ZQCF918_SOURCE_NAME
    assert asian_home.bookmaker == PINNACLE_BOOKMAKER
    assert asian_home.market_line == Decimal("-0.50")
    assert asian_home.odds == Decimal("2.910")
    assert asian_home.snapshot_time == datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("UTC"))
    total_over = next(
        row for row in snapshots if row.market_type == "total_goals" and row.outcome_side == "over"
    )
    assert total_over.odds == Decimal("2.880")
    match_winner_home = next(
        row for row in snapshots if row.market_type == "match_winner" and row.outcome_side == "home"
    )
    assert match_winner_home.odds == Decimal("2.400")


def test_skips_sealed_and_malformed_rows():
    payloads = [
        ZQCF918TimelinePayload(
            market="asian_handicap",
            rows=[
                {
                    "c": "1.91",
                    "d": "-0.5",
                    "e": "1.95",
                    "isFeng2": True,
                    "changeTime": "2026-06-26T10:00:00Z",
                },
                {"c": "封", "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:01:00Z"},
                {"c": "1.92", "d": "-0.25", "e": "1.96", "changeTimeStr": "2026-06-26 18:02:00"},
            ],
            raw_payload={},
        )
    ]

    snapshots = map_zqcf918_timelines(match_id=123, source_fixture_id="4460916", payloads=payloads)

    assert len(snapshots) == 2
    assert {row.outcome_side for row in snapshots} == {"home", "away"}
    assert snapshots[0].snapshot_time == datetime(2026, 6, 26, 10, 2, tzinfo=ZoneInfo("UTC"))
