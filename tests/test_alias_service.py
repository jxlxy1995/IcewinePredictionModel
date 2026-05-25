from icewine_prediction.alias_service import (
    add_external_alias,
    expand_external_names,
    list_external_aliases,
    normalize_alias_name,
)


def test_add_external_alias_upserts_by_source_entity_and_alias(session):
    first = add_external_alias(
        session,
        entity_type="team",
        source_name="oddspapi",
        canonical_name="Wolves",
        alias_name="Wolverhampton Wanderers",
    )
    second = add_external_alias(
        session,
        entity_type="team",
        source_name="oddspapi",
        canonical_name="Wolves",
        alias_name="Wolverhampton Wanderers",
    )

    aliases = list_external_aliases(session, source_name="oddspapi", entity_type="team")

    assert first.id == second.id
    assert len(aliases) == 1
    assert aliases[0].canonical_name == "Wolves"
    assert aliases[0].normalized_alias == normalize_alias_name("Wolverhampton Wanderers")


def test_expand_external_names_returns_aliases_for_canonical_name(session):
    add_external_alias(
        session,
        entity_type="team",
        source_name="oddspapi",
        canonical_name="Wolves",
        alias_name="Wolverhampton Wanderers",
    )

    names = expand_external_names(
        session,
        source_name="oddspapi",
        entity_type="team",
        canonical_name="Wolves",
    )

    assert names == {"Wolves", "Wolverhampton Wanderers"}
