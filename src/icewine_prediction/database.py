from pathlib import Path

from sqlalchemy import create_engine
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
