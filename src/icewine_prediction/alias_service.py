import re
import unicodedata

from sqlalchemy.orm import Session

from icewine_prediction.models import ExternalAlias
from icewine_prediction.time_utils import now_beijing


def normalize_alias_name(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_name)).strip()


def add_external_alias(
    session: Session,
    entity_type: str,
    source_name: str,
    canonical_name: str,
    alias_name: str,
) -> ExternalAlias:
    normalized_alias = normalize_alias_name(alias_name)
    existing = (
        session.query(ExternalAlias)
        .filter_by(
            entity_type=entity_type,
            source_name=source_name,
            normalized_alias=normalized_alias,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.canonical_name = canonical_name
        existing.alias_name = alias_name
        session.commit()
        return existing

    alias = ExternalAlias(
        entity_type=entity_type,
        source_name=source_name,
        canonical_name=canonical_name,
        alias_name=alias_name,
        normalized_alias=normalized_alias,
        created_at=now_beijing(),
    )
    session.add(alias)
    session.commit()
    return alias


def list_external_aliases(
    session: Session,
    source_name: str | None = None,
    entity_type: str | None = None,
) -> list[ExternalAlias]:
    query = session.query(ExternalAlias)
    if source_name is not None:
        query = query.filter_by(source_name=source_name)
    if entity_type is not None:
        query = query.filter_by(entity_type=entity_type)
    return query.order_by(
        ExternalAlias.source_name,
        ExternalAlias.entity_type,
        ExternalAlias.canonical_name,
        ExternalAlias.alias_name,
    ).all()


def expand_external_names(
    session: Session,
    source_name: str,
    entity_type: str,
    canonical_name: str,
) -> set[str]:
    names = {canonical_name}
    aliases = (
        session.query(ExternalAlias)
        .filter_by(
            source_name=source_name,
            entity_type=entity_type,
            canonical_name=canonical_name,
        )
        .all()
    )
    names.update(alias.alias_name for alias in aliases)
    return names
