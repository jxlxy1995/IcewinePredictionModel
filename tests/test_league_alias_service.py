from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.league_alias_service import (
    LeagueAliasConflictError,
    load_zqcf918_league_aliases,
)
from icewine_prediction.models import ExternalAlias
from icewine_prediction.odds_source_match_service import ExternalAliasInput


def _write_config(tmp_path, rows: list[str]) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(["aliases:", *rows]),
        encoding="utf-8",
    )


def test_load_zqcf918_league_aliases_filters_entity_and_source(
    session,
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        [
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: Ekstraklasa (Poland)",
            "    alias_name: 波兰甲",
            "  - entity_type: league",
            "    source_name: the_odds_api",
            "    canonical_name: Ekstraklasa (Poland)",
            "    alias_name: Polish Ekstraklasa",
            "  - entity_type: team",
            "    source_name: zqcf918",
            "    canonical_name: Wolves",
            "    alias_name: Wolverhampton Wanderers",
        ],
    )
    monkeypatch.chdir(tmp_path)
    session.add_all(
        [
            ExternalAlias(
                entity_type="league",
                source_name="zqcf918",
                canonical_name="Ekstraklasa (Poland)",
                alias_name="Ekstraklasa Polska",
                normalized_alias="ekstraklasa polska",
                created_at=datetime(2026, 8, 1, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            ),
            ExternalAlias(
                entity_type="league",
                source_name="the_odds_api",
                canonical_name="Ekstraklasa (Poland)",
                alias_name="Poland Premier",
                normalized_alias="poland premier",
                created_at=datetime(2026, 8, 1, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            ),
        ]
    )
    session.commit()

    aliases = load_zqcf918_league_aliases(session)

    assert ExternalAliasInput("Ekstraklasa (Poland)", "波兰甲") in aliases
    assert ExternalAliasInput("Ekstraklasa (Poland)", "Ekstraklasa Polska") in aliases
    assert ExternalAliasInput("Ekstraklasa (Poland)", "Polish Ekstraklasa") not in aliases
    assert ExternalAliasInput("Wolves", "Wolverhampton Wanderers") not in aliases


def test_load_zqcf918_league_aliases_deduplicates_equivalent_records(
    session,
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        [
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: Ekstraklasa (Poland)",
            "    alias_name: Poland First",
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: Ekstraklasa (Poland)",
            "    alias_name: Poland-First",
        ],
    )
    monkeypatch.chdir(tmp_path)

    aliases = load_zqcf918_league_aliases(session)

    assert aliases == [ExternalAliasInput("Ekstraklasa (Poland)", "Poland First")]


def test_load_zqcf918_league_aliases_keeps_distinct_chinese_aliases(
    session,
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        [
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: Ekstraklasa (Poland)",
            "    alias_name: \u6ce2\u5170\u7532",
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: Urvalsdeild (Iceland)",
            "    alias_name: \u51b0\u5c9b\u8d85",
        ],
    )
    monkeypatch.chdir(tmp_path)

    aliases = load_zqcf918_league_aliases(session)

    assert aliases == [
        ExternalAliasInput("Ekstraklasa (Poland)", "\u6ce2\u5170\u7532"),
        ExternalAliasInput("Urvalsdeild (Iceland)", "\u51b0\u5c9b\u8d85"),
    ]


def test_load_zqcf918_league_aliases_rejects_cross_league_conflicts(
    session,
    tmp_path,
    monkeypatch,
):
    _write_config(
        tmp_path,
        [
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: League One",
            "    alias_name: Shared League",
            "  - entity_type: league",
            "    source_name: zqcf918",
            "    canonical_name: League Two",
            "    alias_name: Shared-League",
        ],
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        LeagueAliasConflictError,
        match="shared league.*League One.*League Two",
    ):
        load_zqcf918_league_aliases(session)
