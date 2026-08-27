from icewine_prediction.sources.oddspapi_bookmaker import (
    normalize_bookmaker_slug,
    to_api_bookmaker_slug,
)


def test_internal_pinnacle_uses_pinnacle_plus_30_api_slug():
    assert to_api_bookmaker_slug("pinnacle") == "pinnacle+30"


def test_other_explicit_bookmakers_are_unchanged():
    assert to_api_bookmaker_slug("sbobet") == "sbobet"


def test_pinnacle_plus_30_is_normalized_to_existing_internal_name():
    assert normalize_bookmaker_slug("pinnacle+30") == "pinnacle"


def test_unknown_slug_is_lowercased_without_conflation():
    assert normalize_bookmaker_slug("ExampleBook") == "examplebook"
