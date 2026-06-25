from collections import defaultdict
from typing import Iterable

from icewine_prediction.models import HistoricalOddsSnapshot


ODDSPAPI_SOURCE_NAME = "oddspapi"
THE_ODDS_API_SOURCE_NAME = "the_odds_api"
PINNACLE_BOOKMAKER = "pinnacle"
PINNACLE_SOURCE_PRIORITY = (THE_ODDS_API_SOURCE_NAME, ODDSPAPI_SOURCE_NAME)


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


def source_label_for_snapshots(snapshots: Iterable[HistoricalOddsSnapshot]) -> str:
    source_names = {snapshot.source_name for snapshot in snapshots}
    if THE_ODDS_API_SOURCE_NAME in source_names:
        return "the_odds_api_historical"
    if ODDSPAPI_SOURCE_NAME in source_names:
        return "oddspapi_historical"
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
