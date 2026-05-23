from datetime import date

import typer
from sqlalchemy import text

from icewine_prediction.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.feature_service import MatchOddsFeatures, list_upcoming_match_odds_features
from icewine_prediction.match_query_service import list_upcoming_matches
from icewine_prediction.recommendation_service import (
    Recommendation,
    build_rule_recommendations_from_features,
)
from icewine_prediction.sample_report_service import (
    TrainingSampleReport,
    build_training_sample_report,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sync_runner import (
    run_history_backfill,
    run_sync_historical_odds,
    run_sync_history,
    run_sync_odds,
    run_sync_results,
    run_sync_upcoming,
)
from icewine_prediction.time_utils import now_beijing
from icewine_prediction.training_sample_service import TrainingSample, list_training_samples

app = typer.Typer(help="冰酒足球预测模型 CLI")
sync_app = typer.Typer(help="数据同步命令")
matches_app = typer.Typer(help="比赛查询命令")
app.add_typer(sync_app, name="sync")
app.add_typer(matches_app, name="matches")
features_app = typer.Typer(help="赔率特征命令")
app.add_typer(features_app, name="features")
recommendations_app = typer.Typer(help="推荐预览命令")
app.add_typer(recommendations_app, name="recommendations")
samples_app = typer.Typer(help="训练样本命令")
app.add_typer(samples_app, name="samples")


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


@sync_app.command("historical-odds")
def sync_historical_odds(days: int = typer.Option(7, "--days")):
    typer.echo(run_sync_historical_odds(days=days))


@sync_app.command("results")
def sync_results(from_date: str, to_date: str):
    typer.echo(run_sync_results(date.fromisoformat(from_date), date.fromisoformat(to_date)))


@sync_app.command("history")
def sync_history(
    league_id: int = typer.Option(..., "--league-id"),
    season: int = typer.Option(..., "--season"),
):
    typer.echo(run_sync_history(league_id=league_id, season=season))


@sync_app.command("backfill-history")
def sync_backfill_history(
    from_season: int = typer.Option(..., "--from-season"),
    to_season: int = typer.Option(..., "--to-season"),
    max_leagues: int = typer.Option(1, "--max-leagues"),
    historical_odds_days: int = typer.Option(0, "--historical-odds-days"),
):
    settings = load_project_settings()
    typer.echo(
        run_history_backfill(
            leagues=settings.leagues,
            from_season=from_season,
            to_season=to_season,
            max_leagues=max_leagues,
            historical_odds_days=historical_odds_days,
        )
    )


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


def _format_decimal(value) -> str:
    if value is None:
        return "-"
    return str(value)


def format_feature_line(
    match,
    features: MatchOddsFeatures,
    display_service: DisplayNameService,
) -> str:
    match_text = format_match_line(match, display_service)
    return (
        f"{match_text} | bookmaker {features.bookmaker_count} | "
        f"亚盘均值 {_format_decimal(features.asian_handicap.mean)} "
        f"分歧 {_format_decimal(features.asian_handicap.disagreement)} | "
        f"主队赔率 {_format_decimal(features.home_odds.mean)} "
        f"客队赔率 {_format_decimal(features.away_odds.mean)} | "
        f"大小球均值 {_format_decimal(features.total_line.mean)} "
        f"分歧 {_format_decimal(features.total_line.disagreement)} | "
        f"大球 {_format_decimal(features.over_odds.mean)} "
        f"小球 {_format_decimal(features.under_odds.mean)}"
    )


def _display_market_type(market_type: str) -> str:
    if market_type == "asian_handicap":
        return "亚盘"
    if market_type == "total_goals":
        return "大小球"
    return market_type


def _display_side(side: str) -> str:
    side_names = {
        "home": "主队",
        "away": "客队",
        "over": "大球",
        "under": "小球",
        "watch": "观望",
    }
    return side_names.get(side, side)


def _format_recommendation_part(recommendation: Recommendation) -> str:
    risk_text = ""
    if recommendation.risk_tags:
        risk_text = f" 风险 {','.join(recommendation.risk_tags)}"
    return (
        f"{_display_market_type(recommendation.market_type)} "
        f"{_display_side(recommendation.side)} "
        f"{recommendation.confidence_grade} "
        f"{recommendation.stake_units}手"
        f"{risk_text}"
    )


def format_recommendation_line(
    match,
    recommendations: list[Recommendation],
    display_service: DisplayNameService,
) -> str:
    match_text = format_match_line(match, display_service)
    recommendation_text = " | ".join(
        _format_recommendation_part(recommendation) for recommendation in recommendations
    )
    return f"{match_text} | {recommendation_text}"


def format_training_sample_line(
    sample: TrainingSample,
    display_service: DisplayNameService,
) -> str:
    kickoff = sample.kickoff_time.strftime("%Y-%m-%d %H:%M")
    league_name = display_service.display_league(sample.league_name)
    home_name = display_service.display_team(sample.home_team_name)
    away_name = display_service.display_team(sample.away_team_name)
    return (
        f"{league_name} {kickoff} {home_name} vs {away_name} | "
        f"比分 {sample.home_score}-{sample.away_score} | "
        f"赛果 {sample.match_result} | "
        f"总进球 {sample.total_goals} | "
        f"样本年龄 {sample.sample_age_days}天 | "
        f"权重 {sample.time_decay_weight} | "
        f"赔率 {'是' if sample.has_odds_snapshot else '否'} | "
        f"亚盘 {sample.asian_handicap_line or '-'} "
        f"主 {sample.home_handicap_result or '-'} 客 {sample.away_handicap_result or '-'} | "
        f"大小球 {sample.total_line or '-'} "
        f"大 {sample.over_result or '-'} 小 {sample.under_result or '-'}"
    )


def _format_counter(counter: dict) -> str:
    return ", ".join(f"{key}: {value}" for key, value in counter.items())


def format_training_sample_report(report: TrainingSampleReport) -> str:
    return "\n".join(
        [
            f"总样本 {report.total_samples}",
            f"有赔率样本 {report.samples_with_odds}",
            f"赔率覆盖率 {report.odds_coverage_ratio}",
            f"按联赛 {_format_counter(report.by_league)}",
            f"按赛季 {_format_counter(report.by_season)}",
            f"按权重 {_format_counter(report.by_weight)}",
        ]
    )


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


@features_app.command("preview")
def features_preview(hours: int = 24):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        rows = list_upcoming_match_odds_features(session, start_time=now_beijing(), hours=hours)
        for row in rows:
            typer.echo(format_feature_line(row.match, row.features, display_service))


@recommendations_app.command("preview")
def recommendations_preview(hours: int = 24):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        rows = list_upcoming_match_odds_features(session, start_time=now_beijing(), hours=hours)
        for row in rows:
            recommendations = build_rule_recommendations_from_features(row.features)
            typer.echo(format_recommendation_line(row.match, recommendations, display_service))


@samples_app.command("preview")
def samples_preview(limit: int = 10):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        for sample in samples:
            typer.echo(format_training_sample_line(sample, display_service))


@samples_app.command("report")
def samples_report():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_training_sample_report(session)
        typer.echo(format_training_sample_report(report))


if __name__ == "__main__":
    app()
