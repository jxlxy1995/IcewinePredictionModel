from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from icewine_prediction.config import DEFAULT_DATABASE_PATH


class Base(DeclarativeBase):
    pass


def create_database_engine(database_path: Path = DEFAULT_DATABASE_PATH) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", future=True)


def create_memory_database() -> Engine:
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


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
        "odds_snapshots": {
            "match_winner_home_odds": "NUMERIC(6, 3)",
            "match_winner_draw_odds": "NUMERIC(6, 3)",
            "match_winner_away_odds": "NUMERIC(6, 3)",
        },
        "training_runs": {
            "away_cover_bucket_threshold_report_path": "VARCHAR(255)",
            "away_cover_bucket_sandbox_report_path": "VARCHAR(255)",
            "total_goals_edge_stability_report_path": "VARCHAR(255)",
            "total_goals_bucket_sandbox_report_path": "VARCHAR(255)",
        },
        "paper_recommendation_records": {
            "scoring_edge": "NUMERIC(8, 4)",
        },
    }
    with engine.begin() as connection:
        if "paper_automation_tasks" not in table_names:
            Base.metadata.tables["paper_automation_tasks"].create(connection, checkfirst=True)
        if "paper_recommendation_group_snapshots" not in table_names:
            Base.metadata.tables["paper_recommendation_group_snapshots"].create(
                connection,
                checkfirst=True,
            )
        _ensure_paper_group_snapshot_unique_index(connection)
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
        if "historical_odds_snapshots" in table_names:
            _ensure_historical_odds_snapshot_unique_constraint(connection)


def _ensure_paper_group_snapshot_unique_index(connection) -> None:
    expected_columns = [
        "snapshot_source",
        "snapshot_version",
        "group_key",
        "signal_record_ids_json",
    ]
    unique_indexes = _sqlite_unique_indexes(
        connection,
        "paper_recommendation_group_snapshots",
    )
    if expected_columns in unique_indexes.values():
        return
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_group_snapshot_identity "
            "ON paper_recommendation_group_snapshots ("
            "snapshot_source, snapshot_version, group_key, signal_record_ids_json)"
        )
    )


def _ensure_historical_odds_snapshot_unique_constraint(connection) -> None:
    expected_columns = [
        "match_id",
        "source_name",
        "bookmaker",
        "market_type",
        "market_id",
        "market_line",
        "outcome_side",
        "snapshot_time",
    ]
    legacy_columns = [
        "match_id",
        "source_name",
        "bookmaker",
        "market_type",
        "market_id",
        "outcome_side",
        "snapshot_time",
    ]
    unique_indexes = _sqlite_unique_indexes(connection, "historical_odds_snapshots")
    if expected_columns in unique_indexes.values():
        return
    if legacy_columns in unique_indexes.values():
        _rebuild_historical_odds_snapshot_table(connection)
        return
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_historical_odds_snapshot "
            "ON historical_odds_snapshots ("
            "match_id, source_name, bookmaker, market_type, market_id, "
            "market_line, outcome_side, snapshot_time)"
        )
    )


def _sqlite_unique_indexes(connection, table_name: str) -> dict[str, list[str]]:
    rows = connection.execute(text(f"PRAGMA index_list('{table_name}')")).all()
    indexes = {}
    for row in rows:
        index_name = row[1]
        is_unique = row[2]
        if not is_unique:
            continue
        column_rows = connection.execute(text(f"PRAGMA index_info('{index_name}')")).all()
        indexes[index_name] = [column_row[2] for column_row in column_rows]
    return indexes


def _rebuild_historical_odds_snapshot_table(connection) -> None:
    from icewine_prediction import models  # noqa: F401

    legacy_table_name = "historical_odds_snapshots_legacy_unique"
    connection.execute(text(f"DROP TABLE IF EXISTS {legacy_table_name}"))
    connection.execute(
        text(
            "ALTER TABLE historical_odds_snapshots "
            f"RENAME TO {legacy_table_name}"
        )
    )
    Base.metadata.tables["historical_odds_snapshots"].create(connection)
    columns = [
        "id",
        "match_id",
        "source_name",
        "source_fixture_id",
        "bookmaker",
        "market_type",
        "market_id",
        "market_name",
        "market_line",
        "outcome_side",
        "odds",
        "snapshot_time",
        "period",
        "raw_payload",
    ]
    column_list = ", ".join(columns)
    connection.execute(
        text(
            f"INSERT INTO historical_odds_snapshots ({column_list}) "
            f"SELECT {column_list} FROM {legacy_table_name}"
        )
    )
    connection.execute(text(f"DROP TABLE {legacy_table_name}"))
