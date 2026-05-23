import pytest

from icewine_prediction.database import (
    create_memory_database,
    create_session_factory,
    initialize_database,
)


@pytest.fixture()
def session():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
