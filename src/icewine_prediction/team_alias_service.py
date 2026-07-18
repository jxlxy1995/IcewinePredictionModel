from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from icewine_prediction.alias_service import list_external_aliases, normalize_alias_name
from icewine_prediction.odds_source_match_service import ExternalAliasInput


DEFAULT_TEAM_ALIAS_CONFIG_PATH = Path("config/external_aliases.yaml")


class TeamAliasConflictError(ValueError):
    pass


def load_global_team_aliases(
    session: Session,
    config_path: Path = DEFAULT_TEAM_ALIAS_CONFIG_PATH,
) -> list[ExternalAliasInput]:
    config_aliases = _load_configured_team_aliases(config_path)
    database_aliases = [
        ExternalAliasInput(
            canonical_name=alias.canonical_name,
            alias_name=alias.alias_name,
        )
        for alias in list_external_aliases(session, entity_type="team")
    ]
    return _deduplicate_team_aliases([*config_aliases, *database_aliases])


def _load_configured_team_aliases(config_path: Path) -> list[ExternalAliasInput]:
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    aliases = []
    for item in payload.get("aliases", []):
        if item.get("entity_type") != "team":
            continue
        canonical_name = item.get("canonical_name")
        alias_name = item.get("alias_name")
        if not canonical_name or not alias_name:
            continue
        aliases.append(
            ExternalAliasInput(
                canonical_name=str(canonical_name),
                alias_name=str(alias_name),
            )
        )
    return aliases


def _deduplicate_team_aliases(
    aliases: list[ExternalAliasInput],
) -> list[ExternalAliasInput]:
    aliases_by_normalized_name: dict[str, ExternalAliasInput] = {}
    for alias in aliases:
        normalized_alias = normalize_alias_name(alias.alias_name)
        existing = aliases_by_normalized_name.get(normalized_alias)
        if existing is None:
            aliases_by_normalized_name[normalized_alias] = alias
            continue
        if normalize_alias_name(existing.canonical_name) != normalize_alias_name(
            alias.canonical_name
        ):
            raise TeamAliasConflictError(
                f"team alias conflict for {normalized_alias!r}: "
                f"{existing.canonical_name!r} vs {alias.canonical_name!r}"
            )
    return list(aliases_by_normalized_name.values())
