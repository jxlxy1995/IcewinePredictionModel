from collections import defaultdict
from typing import Iterable

from icewine_prediction.models import HistoricalOddsSnapshot


ODDSPAPI_SOURCE_NAME = "oddspapi"
THE_ODDS_API_SOURCE_NAME = "the_odds_api"
ZQCF918_SOURCE_NAME = "zqcf918"
PINNACLE_BOOKMAKER = "pinnacle"
SBOBET_BOOKMAKER = "sbobet"
PINNACLE_SOURCE_PRIORITY = (
    THE_ODDS_API_SOURCE_NAME,
    ODDSPAPI_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)
TRUSTED_SNAPSHOT_PRIORITY = (
    (THE_ODDS_API_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ODDSPAPI_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER),
)


def filter_priority_pinnacle_snapshots(
    snapshots: Iterable[HistoricalOddsSnapshot],
    *,
    source_priority: tuple[str, ...] = PINNACLE_SOURCE_PRIORITY,
    bookmaker: str = PINNACLE_BOOKMAKER,
) -> list[HistoricalOddsSnapshot]:
    grouped: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    normalized_bookmaker = bookmaker.lower()
    for snapshot in snapshots:
        if snapshot.bookmaker.lower() != normalized_bookmaker:
            continue
        if snapshot.source_name not in source_priority:
            continue
        grouped[snapshot.match_id].append(snapshot)

    selected: list[HistoricalOddsSnapshot] = []
    for match_id in sorted(grouped):
        match_snapshots = grouped[match_id]
        selected_source = _first_available_source(match_snapshots, source_priority)
        selected.extend(
            snapshot
            for snapshot in match_snapshots
            if snapshot.source_name == selected_source
        )
    return selected


def filter_priority_trusted_snapshots(
    snapshots: Iterable[HistoricalOddsSnapshot],
    *,
    priority: tuple[tuple[str, str], ...] = TRUSTED_SNAPSHOT_PRIORITY,
) -> list[HistoricalOddsSnapshot]:
    grouped: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    normalized_priority = tuple(
        (source_name, bookmaker.lower())
        for source_name, bookmaker in priority
    )
    priority_set = set(normalized_priority)
    for snapshot in snapshots:
        key = (snapshot.source_name, snapshot.bookmaker.lower())
        if key not in priority_set:
            continue
        grouped[snapshot.match_id].append(snapshot)

    selected: list[HistoricalOddsSnapshot] = []
    for match_id in sorted(grouped):
        match_snapshots = grouped[match_id]
        selected_key = _first_available_source_bookmaker(match_snapshots, normalized_priority)
        selected.extend(
            snapshot
            for snapshot in match_snapshots
            if (snapshot.source_name, snapshot.bookmaker.lower()) == selected_key
        )
    return selected


def source_label_for_snapshots(snapshots: Iterable[HistoricalOddsSnapshot]) -> str:
    source_bookmakers = {
        (snapshot.source_name, snapshot.bookmaker.lower())
        for snapshot in snapshots
    }
    if (THE_ODDS_API_SOURCE_NAME, PINNACLE_BOOKMAKER) in source_bookmakers:
        return "the_odds_api_pinnacle_historical"
    if (ODDSPAPI_SOURCE_NAME, PINNACLE_BOOKMAKER) in source_bookmakers:
        return "oddspapi_pinnacle_historical"
    if (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER) in source_bookmakers:
        return "zqcf918_pinnacle_historical"
    if (ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER) in source_bookmakers:
        return "oddspapi_sbobet_historical"
    source_names = {source_name for source_name, _bookmaker in source_bookmakers}
    if THE_ODDS_API_SOURCE_NAME in source_names:
        return "the_odds_api_historical"
    if ODDSPAPI_SOURCE_NAME in source_names:
        return "oddspapi_historical"
    if ZQCF918_SOURCE_NAME in source_names:
        return "zqcf918_historical"
    return "historical"


def _first_available_source(
    snapshots: list[HistoricalOddsSnapshot],
    source_priority: tuple[str, ...],
) -> str:
    available = {snapshot.source_name for snapshot in snapshots}
    for source_name in source_priority:
        if source_name in available:
            return source_name
    return snapshots[0].source_name


def _first_available_source_bookmaker(
    snapshots: list[HistoricalOddsSnapshot],
    priority: tuple[tuple[str, str], ...],
) -> tuple[str, str]:
    available = {
        (snapshot.source_name, snapshot.bookmaker.lower())
        for snapshot in snapshots
    }
    for key in priority:
        if key in available:
            return key
    first = snapshots[0]
    return first.source_name, first.bookmaker.lower()
