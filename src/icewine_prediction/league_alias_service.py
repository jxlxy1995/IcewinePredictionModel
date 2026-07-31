from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from icewine_prediction.alias_service import list_external_aliases, normalize_alias_name
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.odds_source_match_service import ExternalAliasInput


DEFAULT_EXTERNAL_ALIAS_CONFIG_PATH = Path("config/external_aliases.yaml")


class LeagueAliasConflictError(ValueError):
    pass


def load_zqcf918_league_aliases(
    session: Session,
    config_path: Path = DEFAULT_EXTERNAL_ALIAS_CONFIG_PATH,
) -> list[ExternalAliasInput]:
    configured = _load_configured_aliases(config_path)
    database = [
        ExternalAliasInput(alias.canonical_name, alias.alias_name)
        for alias in list_external_aliases(
            session,
            source_name=ZQCF918_SOURCE_NAME,
            entity_type="league",
        )
    ]
    return _deduplicate_aliases([*configured, *database])


def _load_configured_aliases(config_path: Path) -> list[ExternalAliasInput]:
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return [
        ExternalAliasInput(str(item["canonical_name"]), str(item["alias_name"]))
        for item in payload.get("aliases", [])
        if item.get("entity_type") == "league"
        and item.get("source_name") == ZQCF918_SOURCE_NAME
        and item.get("canonical_name")
        and item.get("alias_name")
    ]


def _deduplicate_aliases(
    aliases: list[ExternalAliasInput],
) -> list[ExternalAliasInput]:
    aliases_by_name: dict[str, ExternalAliasInput] = {}
    for alias in aliases:
        normalized_alias = normalize_alias_name(alias.alias_name)
        existing = aliases_by_name.get(normalized_alias)
        if existing is None:
            aliases_by_name[normalized_alias] = alias
            continue
        if normalize_alias_name(existing.canonical_name) != normalize_alias_name(
            alias.canonical_name
        ):
            raise LeagueAliasConflictError(
                f"league alias conflict for {normalized_alias!r}: "
                f"{existing.canonical_name!r} vs {alias.canonical_name!r}"
            )
    return list(aliases_by_name.values())
