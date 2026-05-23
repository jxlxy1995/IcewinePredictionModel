from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from icewine_prediction.cli import format_match_line
from icewine_prediction.display_service import DisplayNameService, DisplayNames


def test_format_match_line_uses_chinese_display_names():
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Serie A": "意甲"},
            teams={"Bologna": "博洛尼亚", "Inter": "国际米兰"},
        )
    )
    match = SimpleNamespace(
        kickoff_time=datetime(2026, 5, 24, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league=SimpleNamespace(name="Serie A"),
        home_team=SimpleNamespace(canonical_name="Bologna"),
        away_team=SimpleNamespace(canonical_name="Inter"),
    )

    assert format_match_line(match, display_service) == "意甲 2026-05-24 00:00 博洛尼亚 vs 国际米兰"
