import pytest

from icewine_prediction.database import (
    create_memory_database,
    create_session_factory,
    initialize_database,
)
from icewine_prediction.oddspapi_sync_runner import GLOBAL_MARKET_DEFINITIONS_CACHE


@pytest.fixture()
def session():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def clear_oddspapi_market_cache():
    GLOBAL_MARKET_DEFINITIONS_CACHE.clear()
    yield
    GLOBAL_MARKET_DEFINITIONS_CACHE.clear()
