from datetime import date

import typer
from sqlalchemy import text

from icewine_prediction.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.match_query_service import list_upcoming_matches
from icewine_prediction.sync_runner import run_sync_odds, run_sync_results, run_sync_upcoming
from icewine_prediction.time_utils import now_beijing

app = typer.Typer(help="冰酒足球预测模型 CLI")
sync_app = typer.Typer(help="数据同步命令")
matches_app = typer.Typer(help="比赛查询命令")
app.add_typer(sync_app, name="sync")
app.add_typer(matches_app, name="matches")


@app.command("version")
def version():
    typer.echo("冰酒足球预测模型 0.1.0")


@app.command("init-db")
def init_db():
    engine = create_database_engine()
    initialize_database(engine)
    typer.echo("数据库初始化完成")


@app.command("db-status")
def db_status():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = session.execute(text("select 1")).scalar_one()
    typer.echo(f"数据库连接正常：{result}")


@sync_app.command("leagues")
def sync_leagues():
    typer.echo("计划同步联赛白名单")


@sync_app.command("upcoming")
def sync_upcoming(days: int = 3):
    typer.echo(run_sync_upcoming(days))


@sync_app.command("odds")
def sync_odds(days: int = 2):
    typer.echo(run_sync_odds(days))


@sync_app.command("results")
def sync_results(from_date: str, to_date: str):
    typer.echo(run_sync_results(date.fromisoformat(from_date), date.fromisoformat(to_date)))


@sync_app.command("all")
def sync_all(days: int = 3):
    typer.echo(run_sync_upcoming(days))
    typer.echo(run_sync_odds(days))


def format_match_line(match, display_service: DisplayNameService) -> str:
    kickoff = match.kickoff_time.strftime("%Y-%m-%d %H:%M")
    league_name = display_service.display_league(match.league.name)
    home_name = display_service.display_team(match.home_team.canonical_name)
    away_name = display_service.display_team(match.away_team.canonical_name)
    return f"{league_name} {kickoff} {home_name} vs {away_name}"


@matches_app.command("upcoming")
def matches_upcoming(hours: int = 24):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        matches = list_upcoming_matches(session, start_time=now_beijing(), hours=hours)
        for match in matches:
            typer.echo(format_match_line(match, display_service))


if __name__ == "__main__":
    app()
