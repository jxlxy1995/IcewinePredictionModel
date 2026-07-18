from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.models import ExternalAlias
from icewine_prediction.odds_source_match_service import ExternalAliasInput
from icewine_prediction.team_alias_service import (
    TeamAliasConflictError,
    load_global_team_aliases,
)


def _write_alias_config(tmp_path, lines: list[str]) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(["aliases:", *lines]),
        encoding="utf-8",
    )


def test_load_global_team_aliases_ignores_source_scope(session, tmp_path, monkeypatch):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Ham-Kam",
            "    alias_name: HamKam",
            "  - entity_type: team",
            "    source_name: the_odds_api",
            "    canonical_name: Sichuan Jiuniu",
            "    alias_name: Shenzhen Peng City",
        ],
    )
    monkeypatch.chdir(tmp_path)
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name="another_odds_source",
            canonical_name="Wolves",
            alias_name="Wolverhampton Wanderers",
            normalized_alias="wolverhampton wanderers",
            created_at=datetime(2026, 7, 18, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    session.commit()

    aliases = load_global_team_aliases(session)

    assert ExternalAliasInput("Ham-Kam", "HamKam") in aliases
    assert ExternalAliasInput("Sichuan Jiuniu", "Shenzhen Peng City") in aliases
    assert ExternalAliasInput("Wolves", "Wolverhampton Wanderers") in aliases


def test_load_global_team_aliases_deduplicates_equivalent_records(
    session,
    tmp_path,
    monkeypatch,
):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Ham-Kam",
            "    alias_name: HamKam",
        ],
    )
    monkeypatch.chdir(tmp_path)
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name="the_odds_api",
            canonical_name="Ham-Kam",
            alias_name="HAMKAM",
            normalized_alias="hamkam",
            created_at=datetime(2026, 7, 18, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    session.commit()

    aliases = load_global_team_aliases(session)

    assert aliases == [ExternalAliasInput("Ham-Kam", "HamKam")]


def test_load_global_team_aliases_rejects_cross_team_conflicts(
    session,
    tmp_path,
    monkeypatch,
):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Team One",
            "    alias_name: Shared Name",
            "  - entity_type: team",
            "    source_name: the_odds_api",
            "    canonical_name: Team Two",
            "    alias_name: Shared-Name",
        ],
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        TeamAliasConflictError,
        match="shared name.*Team One.*Team Two",
    ):
        load_global_team_aliases(session)
