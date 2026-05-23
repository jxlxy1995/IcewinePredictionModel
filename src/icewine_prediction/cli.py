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
from icewine_prediction.history_coverage_service import (
    LeagueCoverageSummary,
    build_history_coverage_report,
)
from icewine_prediction.historical_performance_service import (
    HistoricalPerformanceFilters,
    HistoricalPerformanceReport,
    build_historical_performance_report,
)
from icewine_prediction.match_query_service import list_upcoming_matches
from icewine_prediction.model_training_service import (
    BaselineResultEvaluation,
    evaluate_baseline_result_model,
    train_baseline_result_model,
    train_league_team_strength_goal_model,
    train_team_strength_goal_model,
)
from icewine_prediction.oddspapi_sync_runner import (
    build_oddspapi_probe_report,
    build_oddspapi_sync_plan,
    run_oddspapi_sync,
)
from icewine_prediction.recommendation_service import (
    Recommendation,
    build_model_recommendations_from_features,
    build_rule_recommendations_from_features,
)
from icewine_prediction.record_service import (
    RecordGroupSummary,
    RecordReport,
    build_record_report,
    list_pending_records,
    record_recommendations_for_match,
    settle_pending_records,
)
from icewine_prediction.recommendation_history_service import enrich_recommendations_with_history
from icewine_prediction.sample_report_service import (
    TrainingSampleReport,
    build_training_sample_report,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sync_runner import (
    build_history_backfill_plan,
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
history_app = typer.Typer(help="历史数据命令")
app.add_typer(history_app, name="history")
features_app = typer.Typer(help="赔率特征命令")
app.add_typer(features_app, name="features")
recommendations_app = typer.Typer(help="推荐预览命令")
app.add_typer(recommendations_app, name="recommendations")
samples_app = typer.Typer(help="训练样本命令")
app.add_typer(samples_app, name="samples")
models_app = typer.Typer(help="模型训练命令")
app.add_typer(models_app, name="models")
records_app = typer.Typer(help="推荐记录命令")
app.add_typer(records_app, name="records")
odds_source_app = typer.Typer(help="外部赔率源命令")
app.add_typer(odds_source_app, name="odds-source")


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


@sync_app.command("backfill-plan")
def sync_backfill_plan(
    from_season: int = typer.Option(..., "--from-season"),
    to_season: int = typer.Option(..., "--to-season"),
    max_leagues: int = typer.Option(1, "--max-leagues"),
):
    settings = load_project_settings()
    typer.echo(
        build_history_backfill_plan(
            leagues=settings.leagues,
            from_season=from_season,
            to_season=to_season,
            max_leagues=max_leagues,
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
    explanation_parts = []
    if recommendation.market_line is not None:
        explanation_parts.append(f"线 {recommendation.market_line}")
    if recommendation.model_probability is not None:
        explanation_parts.append(f"模型概率 {recommendation.model_probability}")
    if recommendation.market_implied_probability is not None:
        explanation_parts.append(f"隐含概率 {recommendation.market_implied_probability}")
    if recommendation.model_probability is not None:
        explanation_parts.append(f"edge {recommendation.edge}")
    if recommendation.historical_sample_count is not None:
        history_text = f"历史 {recommendation.historical_sample_count}场"
        if recommendation.historical_roi is not None:
            history_text = f"{history_text} ROI {recommendation.historical_roi}"
        explanation_parts.append(history_text)
    if (
        recommendation.home_expected_goals is not None
        and recommendation.away_expected_goals is not None
    ):
        explanation_parts.append(
            f"期望进球 {recommendation.home_expected_goals}-{recommendation.away_expected_goals}"
        )
    explanation_text = ""
    if explanation_parts:
        explanation_text = f" {' '.join(explanation_parts)}"
    return (
        f"{_display_market_type(recommendation.market_type)} "
        f"{_display_side(recommendation.side)} "
        f"{recommendation.confidence_grade} "
        f"{recommendation.stake_units}手"
        f"{explanation_text}"
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


def format_record_line(record, display_service: DisplayNameService) -> str:
    kickoff = record.kickoff_time.strftime("%Y-%m-%d %H:%M")
    league_name = display_service.display_league(record.league_name)
    home_name = display_service.display_team(record.home_team_name)
    away_name = display_service.display_team(record.away_team_name)
    return (
        f"{league_name} {kickoff} {home_name} vs {away_name} | "
        f"{_display_market_type(record.market_type)} {_display_side(record.side)} "
        f"{record.market_line} | {record.confidence_grade} {record.stake_units}手 | "
        f"{record.status}"
    )


def _format_record_group_summary(name: str, summary: RecordGroupSummary) -> str:
    return (
        f"{name}: {summary.record_count}场 "
        f"手数 {summary.stake_units} "
        f"盈亏 {summary.profit_units} "
        f"ROI {summary.roi}"
    )


def _format_record_groups(title: str, groups: dict[str, RecordGroupSummary]) -> str:
    if not groups:
        return f"{title} -"
    group_text = " | ".join(
        _format_record_group_summary(name, summary) for name, summary in groups.items()
    )
    return f"{title} {group_text}"


def format_record_report(report: RecordReport) -> str:
    return "\n".join(
        [
            f"总推荐 {report.total_records}",
            f"已结算 {report.settled_records}",
            f"待结算 {report.pending_records}",
            f"总手数 {report.total_stake_units}",
            f"总盈亏 {report.total_profit_units}",
            f"ROI {report.roi}",
            _format_record_groups("按结果", report.by_settlement_result),
            _format_record_groups("按edge", report.by_edge_bucket),
            _format_record_groups("按盘口", report.by_market_type),
            _format_record_groups("按信心", report.by_confidence_grade),
            _format_record_groups("按联赛", report.by_league),
        ]
    )


def format_historical_performance_report(report: HistoricalPerformanceReport) -> str:
    return "\n".join(
        [
            f"历史样本 {report.total.record_count}",
            f"总手数 {report.total.stake_units}",
            f"总盈亏 {report.total.profit_units}",
            f"ROI {report.total.roi}",
            _format_record_groups("按结果", report.by_settlement_result),
            _format_record_groups("按edge", report.by_edge_bucket),
            _format_record_groups("按盘口", report.by_market_type),
            _format_record_groups("按方向", report.by_side),
            _format_record_groups("按信心", report.by_confidence_grade),
            _format_record_groups("按联赛", report.by_league),
        ]
    )


def format_history_coverage_line(summary: LeagueCoverageSummary) -> str:
    return (
        f"{summary.league_name} {summary.country_or_region} | "
        f"总比赛 {summary.total_matches} "
        f"已完赛 {summary.finished_matches} "
        f"有比分 {summary.scored_matches} | "
        f"有赔率 {summary.matches_with_odds} "
        f"有亚盘 {summary.matches_with_asian_handicap} "
        f"有大小球 {summary.matches_with_total_goals} | "
        f"赔率覆盖 {summary.odds_coverage_ratio} "
        f"亚盘覆盖 {summary.asian_handicap_coverage_ratio} "
        f"大小球覆盖 {summary.total_goals_coverage_ratio}"
    )


def format_history_coverage_report(report: list[LeagueCoverageSummary]) -> str:
    if not report:
        return "暂无历史覆盖率数据"
    return "\n".join(format_history_coverage_line(summary) for summary in report)


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
    league_lines = [
        (
            f"{league_name}: \u603b\u6837\u672c {coverage.total_samples} "
            f"\u6709\u8d54\u7387 {coverage.samples_with_odds} "
            f"\u4e9a\u76d8 {coverage.samples_with_asian_handicap} "
            f"\u5927\u5c0f\u7403 {coverage.samples_with_total_goals}"
        )
        for league_name, coverage in sorted(
            report.by_league.items(),
            key=lambda item: item[1].total_samples,
            reverse=True,
        )
    ]
    return "\n".join(
        [
            f"\u603b\u6837\u672c {report.total_samples}"
            f" / \u6709\u8d54\u7387\u6837\u672c {report.samples_with_odds}"
            f" / \u4e9a\u76d8\u6837\u672c {report.samples_with_asian_handicap}"
            f" / \u5927\u5c0f\u7403\u6837\u672c {report.samples_with_total_goals}",
            f"\u8d54\u7387\u8986\u76d6\u7387 {report.odds_coverage_ratio}"
            f" / \u4e9a\u76d8\u8986\u76d6\u7387 {report.asian_handicap_coverage_ratio}"
            f" / \u5927\u5c0f\u7403\u8986\u76d6\u7387 {report.total_goals_coverage_ratio}",
            f"\u6309\u8054\u8d5b {'; '.join(league_lines)}",
            f"\u6309\u8d5b\u5b63 {_format_counter(report.by_season)}",
            f"\u6309\u6743\u91cd {_format_counter(report.by_weight)}",
        ]
    )


def format_baseline_result_evaluation(evaluation: BaselineResultEvaluation) -> str:
    return "\n".join(
        [
            f"训练样本 {evaluation.train_sample_count}",
            f"验证样本 {evaluation.validation_sample_count}",
            f"主队期望进球 {evaluation.home_expected_goals}",
            f"客队期望进球 {evaluation.away_expected_goals}",
            f"准确率 {evaluation.accuracy}",
            f"log loss {evaluation.average_log_loss}",
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


@recommendations_app.command("model-preview")
def recommendations_model_preview(
    hours: int = typer.Option(24, "--hours"),
    sample_limit: int = typer.Option(1000, "--sample-limit"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        samples = list_training_samples(session, limit=sample_limit)
        model = train_league_team_strength_goal_model(samples)
        rows = list_upcoming_match_odds_features(session, start_time=now_beijing(), hours=hours)
        for row in rows:
            recommendations = build_model_recommendations_from_features(
                features=row.features,
                model=model,
                league_name=row.match.league.name,
                home_team_name=row.match.home_team.canonical_name,
                away_team_name=row.match.away_team.canonical_name,
            )
            recommendations = enrich_recommendations_with_history(session, recommendations)
            typer.echo(format_recommendation_line(row.match, recommendations, display_service))


@recommendations_app.command("record")
def recommendations_record(
    hours: int = typer.Option(24, "--hours"),
    sample_limit: int = typer.Option(1000, "--sample-limit"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    total_inserted = 0
    with session_factory() as session:
        samples = list_training_samples(session, limit=sample_limit)
        model = train_league_team_strength_goal_model(samples)
        rows = list_upcoming_match_odds_features(session, start_time=now_beijing(), hours=hours)
        recorded_at = now_beijing()
        for row in rows:
            recommendations = build_model_recommendations_from_features(
                features=row.features,
                model=model,
                league_name=row.match.league.name,
                home_team_name=row.match.home_team.canonical_name,
                away_team_name=row.match.away_team.canonical_name,
            )
            recommendations = enrich_recommendations_with_history(session, recommendations)
            total_inserted += record_recommendations_for_match(
                session=session,
                match=row.match,
                recommendations=recommendations,
                features=row.features,
                recorded_at=recorded_at,
            )
    typer.echo(f"录入推荐 {total_inserted}")


@records_app.command("pending")
def records_pending():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        for record in list_pending_records(session):
            typer.echo(format_record_line(record, display_service))


@records_app.command("settle")
def records_settle():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        settled_count = settle_pending_records(session)
    typer.echo(f"结算推荐 {settled_count}")


@records_app.command("report")
def records_report():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_record_report(session)
        typer.echo(format_record_report(report))


@records_app.command("performance")
def records_performance(
    market_type: str | None = typer.Option(None, "--market-type"),
    side: str | None = typer.Option(None, "--side"),
    league_name: str | None = typer.Option(None, "--league-name"),
    edge_bucket: str | None = typer.Option(None, "--edge-bucket"),
    confidence_grade: str | None = typer.Option(None, "--confidence-grade"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    filters = HistoricalPerformanceFilters(
        market_type=market_type,
        side=side,
        league_name=league_name,
        edge_bucket=edge_bucket,
        confidence_grade=confidence_grade,
    )
    with session_factory() as session:
        report = build_historical_performance_report(session, filters)
        typer.echo(format_historical_performance_report(report))


@odds_source_app.command("oddspapi-plan")
def odds_source_oddspapi_plan(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
):
    typer.echo(build_oddspapi_sync_plan(season=season, max_matches=max_matches))


@odds_source_app.command("oddspapi-fetch")
def odds_source_oddspapi_fetch(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
    request_budget: int = typer.Option(50, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    max_snapshots_per_match: int = typer.Option(200, "--max-snapshots-per-match"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
):
    typer.echo(
        run_oddspapi_sync(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            skip_match_ids=_parse_id_set(skip_match_ids),
            progress_callback=typer.echo,
        )
    )


@odds_source_app.command("oddspapi-probe")
def odds_source_oddspapi_probe(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
    request_budget: int = typer.Option(50, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
):
    typer.echo(
        build_oddspapi_probe_report(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            skip_match_ids=_parse_id_set(skip_match_ids),
        )
    )


def _parse_id_set(value: str) -> set[int]:
    if not value.strip():
        return set()
    return {int(item.strip()) for item in value.split(",") if item.strip()}


@history_app.command("coverage")
def history_coverage(season: int | None = typer.Option(None, "--season")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_history_coverage_report(session, season=season)
        typer.echo(format_history_coverage_report(report))


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
def samples_report(season: int | None = typer.Option(None, "--season")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_training_sample_report(session, season=season)
        typer.echo(format_training_sample_report(report))


@models_app.command("train-baseline")
def models_train_baseline(limit: int = typer.Option(1000, "--limit")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        evaluation = evaluate_baseline_result_model(samples)
        typer.echo(format_baseline_result_evaluation(evaluation))


if __name__ == "__main__":
    app()
