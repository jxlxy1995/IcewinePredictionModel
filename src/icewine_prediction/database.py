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
    missing_columns_by_table = {
        "leagues": {
            "logo_url": "VARCHAR(255)",
            "flag_url": "VARCHAR(255)",
            "standings_supported": "BOOLEAN",
        },
        "teams": {
            "logo_url": "VARCHAR(255)",
        },
        "matches": {
            "season": "INTEGER",
            "league_round": "VARCHAR(120)",
            "referee": "VARCHAR(120)",
            "fixture_timezone": "VARCHAR(80)",
            "fixture_timestamp": "INTEGER",
            "first_period_started_at": "INTEGER",
            "second_period_started_at": "INTEGER",
            "venue_id": "INTEGER",
            "venue_name": "VARCHAR(160)",
            "venue_city": "VARCHAR(120)",
            "status_long": "VARCHAR(80)",
            "status_short": "VARCHAR(20)",
            "elapsed": "INTEGER",
            "extra": "INTEGER",
            "home_winner": "BOOLEAN",
            "away_winner": "BOOLEAN",
            "halftime_home_score": "INTEGER",
            "halftime_away_score": "INTEGER",
            "fulltime_home_score": "INTEGER",
            "fulltime_away_score": "INTEGER",
            "extratime_home_score": "INTEGER",
            "extratime_away_score": "INTEGER",
            "penalty_home_score": "INTEGER",
            "penalty_away_score": "INTEGER",
        },
        "odds_source_matches": {
            "historical_odds_status": "VARCHAR(40)",
            "historical_odds_checked_at": "DATETIME",
            "historical_odds_error": "TEXT",
        },
    }
    with engine.begin() as connection:
        for table_name, columns in missing_columns_by_table.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
        if "external_aliases" in table_names:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_external_alias "
                    "ON external_aliases (entity_type, source_name, normalized_alias)"
                )
            )
