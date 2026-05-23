import typer
from sqlalchemy import text

from icewine_prediction.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)

app = typer.Typer(help="冰酒足球预测模型 CLI")
sync_app = typer.Typer(help="数据同步命令")
app.add_typer(sync_app, name="sync")


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
    typer.echo(f"计划同步未来 {days} 天赛程")


@sync_app.command("odds")
def sync_odds(days: int = 2):
    typer.echo(f"计划同步未来 {days} 天赔率")


@sync_app.command("results")
def sync_results(from_date: str, to_date: str):
    typer.echo(f"计划同步赛果：{from_date} 至 {to_date}")


@sync_app.command("all")
def sync_all(days: int = 3):
    typer.echo(f"计划同步全部数据，未来 {days} 天")


if __name__ == "__main__":
    app()
