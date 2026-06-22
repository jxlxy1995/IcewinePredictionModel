from pathlib import Path
import sqlite3

from sqlalchemy import inspect

from icewine_prediction.database import create_database_engine, initialize_database


def test_initialize_database_adds_match_detail_columns_to_existing_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        create table leagues (
            id integer primary key,
            name varchar(120) not null,
            country_or_region varchar(80) not null,
            level integer not null,
            is_enabled boolean not null,
            priority integer not null,
            source_name varchar(80),
            source_league_id varchar(120),
            aliases text
        )
        """
    )
    connection.execute(
        """
        create table teams (
            id integer primary key,
            canonical_name varchar(120) not null,
            english_name varchar(120),
            country_or_region varchar(80),
            source_name varchar(80),
            source_team_id varchar(120),
            aliases text
        )
        """
    )
    connection.execute(
        """
        create table matches (
            id integer primary key,
            league_id integer not null,
            home_team_id integer not null,
            away_team_id integer not null,
            kickoff_time datetime not null,
            status varchar(40) not null,
            home_score integer,
            away_score integer,
            source_name varchar(80),
            source_match_id varchar(120)
        )
        """
    )
    connection.close()

    engine = create_database_engine(database_path)
    initialize_database(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    league_columns = {column["name"] for column in inspector.get_columns("leagues")}
    team_columns = {column["name"] for column in inspector.get_columns("teams")}
    match_columns = {column["name"] for column in inspector.get_columns("matches")}
    assert {
        "odds_source_matches",
        "historical_odds_snapshots",
        "historical_odds_raw_snapshots",
        "external_aliases",
        "data_sync_run_items",
    }.issubset(table_names)
    assert {"logo_url", "flag_url", "standings_supported"}.issubset(league_columns)
    assert "logo_url" in team_columns
    assert {
        "league_round",
        "venue_name",
        "status_long",
        "halftime_home_score",
        "penalty_away_score",
    }.issubset(match_columns)
    assert "training_runs" in table_names


def test_initialize_database_adds_paper_scoring_edge_to_existing_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        create table paper_recommendation_records (
            id integer primary key,
            match_id integer not null,
            source_match_id varchar(120),
            created_at datetime not null,
            updated_at datetime not null,
            league_name varchar(120) not null,
            home_team_name varchar(120) not null,
            away_team_name varchar(120) not null,
            kickoff_time datetime not null,
            strategy_key varchar(80) not null,
            strategy_display_name varchar(120) not null,
            model_name varchar(120) not null,
            market_type varchar(40) not null,
            side varchar(20) not null,
            original_market_line numeric(5, 2) not null,
            original_odds numeric(6, 3) not null,
            current_market_line numeric(5, 2) not null,
            current_odds numeric(6, 3) not null,
            edge numeric(8, 4) not null,
            stake_units numeric(6, 2) not null,
            status varchar(20) not null
        )
        """
    )
    connection.close()

    engine = create_database_engine(database_path)
    initialize_database(engine)

    inspector = inspect(engine)
    paper_columns = {column["name"] for column in inspector.get_columns("paper_recommendation_records")}
    assert "scoring_edge" in paper_columns


def test_initialize_database_creates_paper_group_snapshots_for_existing_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        create table paper_recommendation_records (
            id integer primary key,
            match_id integer not null,
            source_match_id varchar(120),
            created_at datetime not null,
            updated_at datetime not null,
            league_name varchar(120) not null,
            home_team_name varchar(120) not null,
            away_team_name varchar(120) not null,
            kickoff_time datetime not null,
            strategy_key varchar(80) not null,
            strategy_display_name varchar(120) not null,
            model_name varchar(120) not null,
            market_type varchar(40) not null,
            side varchar(20) not null,
            original_market_line numeric(5, 2) not null,
            original_odds numeric(6, 3) not null,
            current_market_line numeric(5, 2) not null,
            current_odds numeric(6, 3) not null,
            edge numeric(8, 4) not null,
            stake_units numeric(6, 2) not null,
            status varchar(20) not null
        )
        """
    )
    connection.close()

    engine = create_database_engine(database_path)
    initialize_database(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    snapshot_columns = {
        column["name"]
        for column in inspector.get_columns("paper_recommendation_group_snapshots")
    }
    assert "paper_recommendation_group_snapshots" in table_names
    assert {
        "snapshot_source",
        "snapshot_version",
        "group_key",
        "signal_record_ids_json",
        "confidence_score",
        "suggested_stake_units",
        "line_bucket",
        "is_backfilled",
    }.issubset(snapshot_columns)


def test_initialize_database_rebuilds_historical_odds_unique_index_with_market_line(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        create table historical_odds_snapshots (
            id integer primary key,
            match_id integer not null,
            source_name varchar(80) not null,
            source_fixture_id varchar(120) not null,
            bookmaker varchar(80) not null,
            market_type varchar(40) not null,
            market_id varchar(80) not null,
            market_name varchar(120) not null,
            market_line numeric(6, 2) not null,
            outcome_side varchar(20) not null,
            odds numeric(8, 3) not null,
            snapshot_time datetime not null,
            period varchar(40) not null,
            raw_payload text,
            constraint uq_historical_odds_snapshot unique (
                match_id,
                source_name,
                bookmaker,
                market_type,
                market_id,
                outcome_side,
                snapshot_time
            )
        )
        """
    )
    connection.close()

    engine = create_database_engine(database_path)
    initialize_database(engine)

    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        insert into historical_odds_snapshots (
            match_id,
            source_name,
            source_fixture_id,
            bookmaker,
            market_type,
            market_id,
            market_name,
            market_line,
            outcome_side,
            odds,
            snapshot_time,
            period
        )
        values
            (1, 'oddspapi', 'fixture-1', 'pinnacle', 'total_goals', 'total',
             'Over Under', 2.5, 'over', 1.91, '2026-05-23 12:00:00', 'fulltime'),
            (1, 'oddspapi', 'fixture-1', 'pinnacle', 'total_goals', 'total',
             'Over Under', 2.75, 'over', 1.95, '2026-05-23 12:00:00', 'fulltime')
        """
    )
    connection.close()
