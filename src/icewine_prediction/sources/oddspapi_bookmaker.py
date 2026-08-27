PINNACLE_INTERNAL_BOOKMAKER = "pinnacle"
PINNACLE_API_BOOKMAKER = "pinnacle+30"


def to_api_bookmaker_slug(bookmaker: str) -> str:
    slug = str(bookmaker).strip().lower()
    if slug == PINNACLE_INTERNAL_BOOKMAKER:
        return PINNACLE_API_BOOKMAKER
    return slug


def normalize_bookmaker_slug(bookmaker: str) -> str:
    slug = str(bookmaker).strip().lower()
    if slug == PINNACLE_API_BOOKMAKER:
        return PINNACLE_INTERNAL_BOOKMAKER
    return slug
