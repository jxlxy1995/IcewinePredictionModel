from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from icewine_prediction.config import DEFAULT_DATABASE_PATH


class Base(DeclarativeBase):
    pass


def create_database_engine(database_path: Path = DEFAULT_DATABASE_PATH) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", future=True)


def create_memory_database() -> Engine:
    return create_engine("sqlite:///:memory:", future=True)


def create_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def initialize_database(engine: Engine) -> None:
    from icewine_prediction import models  # noqa: F401

    Base.metadata.create_all(engine)
    _ensure_sqlite_schema(engine)


def _ensure_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "matches" not in table_names:
        return
    match_columns = {column["name"] for column in inspector.get_columns("matches")}
    if "season" in match_columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE matches ADD COLUMN season INTEGER"))
