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
    assert {"odds_source_matches", "historical_odds_snapshots"}.issubset(table_names)
    assert {"logo_url", "flag_url", "standings_supported"}.issubset(league_columns)
    assert "logo_url" in team_columns
    assert {
        "league_round",
        "venue_name",
        "status_long",
        "halftime_home_score",
        "penalty_away_score",
    }.issubset(match_columns)
