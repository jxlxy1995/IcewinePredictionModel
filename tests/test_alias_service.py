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


def test_normalize_alias_name_preserves_unicode_letters_and_latin_compatibility():
    assert normalize_alias_name("T\u00fcrkiye") == "turkiye"
    assert normalize_alias_name("\u0141\u00f3d\u017a") == "odz"
    assert normalize_alias_name("\u6ce2\u5170\u7532") == "\u6ce2\u5170\u7532"
    assert normalize_alias_name("\u51b0\u5c9b-\u8d85") == "\u51b0\u5c9b \u8d85"


def test_add_external_alias_keeps_distinct_chinese_aliases(session):
    add_external_alias(
        session,
        entity_type="league",
        source_name="zqcf918",
        canonical_name="Ekstraklasa (Poland)",
        alias_name="\u6ce2\u5170\u7532",
    )
    add_external_alias(
        session,
        entity_type="league",
        source_name="zqcf918",
        canonical_name="Urvalsdeild (Iceland)",
        alias_name="\u51b0\u5c9b\u8d85",
    )

    aliases = list_external_aliases(
        session,
        source_name="zqcf918",
        entity_type="league",
    )

    assert [(alias.canonical_name, alias.normalized_alias) for alias in aliases] == [
        ("Ekstraklasa (Poland)", "\u6ce2\u5170\u7532"),
        ("Urvalsdeild (Iceland)", "\u51b0\u5c9b\u8d85"),
    ]


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
