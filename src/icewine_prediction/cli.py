from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from sqlalchemy import text

from icewine_prediction.alias_service import add_external_alias, list_external_aliases
from icewine_prediction.baseline_training_dataset_service import (
    BaselineTrainingDataset,
    build_baseline_training_dataset,
    write_baseline_training_dataset_csv,
    write_baseline_training_dataset_report,
)
from icewine_prediction.baseline_training_dataset_qa_service import (
    BaselineTrainingDatasetQaReport,
    build_baseline_training_dataset_qa_report,
    write_baseline_training_dataset_qa_report,
)
from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    BaselineTrainingDatasetMarketBaselineReport,
    build_baseline_training_dataset_market_baseline_report,
    write_baseline_training_dataset_market_baseline_report,
)
from icewine_prediction.baseline_feature_set_service import (
    BaselineFeatureSet,
    build_baseline_feature_set,
    write_baseline_feature_set_csv,
    write_baseline_feature_set_report,
)
from icewine_prediction.baseline_dynamic_feature_set_service import (
    BaselineDynamicFeatureSet,
    build_baseline_dynamic_feature_set,
    write_baseline_dynamic_feature_set_csv,
    write_baseline_dynamic_feature_set_report,
)
from icewine_prediction.baseline_edge_backtest_service import (
    BaselineEdgeBacktestReport,
    build_baseline_edge_backtest_report,
    write_baseline_edge_backtest_report,
)
from icewine_prediction.baseline_walk_forward_edge_service import (
    BaselineWalkForwardEdgeReport,
    build_baseline_walk_forward_edge_report,
    write_baseline_walk_forward_edge_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import (
    BaselineRecommendationSandboxReport,
    build_baseline_recommendation_sandbox_report,
    write_baseline_recommendation_sandbox_report,
)
from icewine_prediction.baseline_walk_forward_sandbox_service import (
    BaselineWalkForwardSandboxReport,
    build_baseline_walk_forward_sandbox_report,
    write_baseline_walk_forward_sandbox_report,
)
from icewine_prediction.baseline_away_cover_stability_service import (
    BaselineAwayCoverStabilityReport,
    build_baseline_away_cover_stability_report,
    write_baseline_away_cover_stability_report,
)
from icewine_prediction.baseline_away_cover_bucket_threshold_service import (
    BaselineAwayCoverBucketThresholdReport,
    build_baseline_away_cover_bucket_threshold_report,
    write_baseline_away_cover_bucket_threshold_report,
)
from icewine_prediction.baseline_away_cover_bucket_sandbox_service import (
    BaselineAwayCoverBucketSandboxReport,
    build_baseline_away_cover_bucket_sandbox_report,
    write_baseline_away_cover_bucket_sandbox_report,
)
from icewine_prediction.baseline_total_goals_edge_stability_service import (
    BaselineTotalGoalsEdgeStabilityReport,
    build_baseline_total_goals_edge_stability_report,
    write_baseline_total_goals_edge_stability_report,
)
from icewine_prediction.baseline_total_goals_bucket_sandbox_service import (
    BaselineTotalGoalsBucketSandboxReport,
    build_baseline_total_goals_bucket_sandbox_report,
    write_baseline_total_goals_bucket_sandbox_report,
)
from icewine_prediction.baseline_total_goals_v3_signal_research_service import (
    BaselineTotalGoalsV3SignalResearchReport,
    build_baseline_total_goals_v3_signal_research_report,
    write_baseline_total_goals_v3_signal_research_report,
)
from icewine_prediction.baseline_home_cover_signal_research_service import (
    BaselineHomeCoverSignalResearchReport,
    build_baseline_home_cover_signal_research_report,
    write_baseline_home_cover_signal_research_report,
)
from icewine_prediction.baseline_model_consensus_signal_research_service import (
    BaselineModelConsensusSignalResearchReport,
    build_baseline_model_consensus_signal_research_report,
    write_baseline_model_consensus_signal_research_report,
)
from icewine_prediction.baseline_t15_signal_comparison_service import (
    BaselineT15SignalComparisonReport,
    build_baseline_t15_signal_comparison_report,
    write_baseline_t15_signal_comparison_report,
)
from icewine_prediction.baseline_execution_robustness_service import (
    BaselineExecutionRobustnessReport,
    build_baseline_execution_robustness_report,
    write_baseline_execution_robustness_report,
)
from icewine_prediction.baseline_execution_robustness_grid_service import (
    BaselineExecutionRobustnessGridReport,
    build_baseline_execution_robustness_grid_report,
    write_baseline_execution_robustness_grid_report,
)
from icewine_prediction.baseline_execution_robustness_filter_service import (
    BaselineExecutionRobustnessFilterReport,
    build_baseline_execution_robustness_filter_report,
    write_baseline_execution_robustness_filter_report,
)
from icewine_prediction.bookmaker_overlap_comparison_service import (
    BookmakerOverlapComparisonReport,
    build_bookmaker_overlap_comparison_report,
    write_bookmaker_overlap_comparison_report,
)
from icewine_prediction.bookmaker_replay_comparison_service import (
    BookmakerReplayComparisonReport,
    build_bookmaker_replay_comparison_report,
    write_bookmaker_replay_comparison_report,
)
from icewine_prediction.baseline_paper_discovery_alignment_service import (
    BaselinePaperDiscoveryAlignmentReport,
    build_baseline_paper_discovery_alignment_report,
    write_baseline_paper_discovery_alignment_report,
)
from icewine_prediction.baseline_asian_handicap_model_service import (
    BaselineAsianHandicapModelReport,
    build_baseline_asian_handicap_model_report,
    write_baseline_asian_handicap_model_report,
)
from icewine_prediction.baseline_match_winner_model_service import (
    BaselineMatchWinnerModelReport,
    build_baseline_match_winner_model_report,
    write_baseline_match_winner_model_report,
)
from icewine_prediction.baseline_market_diagnostics_service import (
    BaselineMarketDiagnosticsReport,
    build_baseline_market_diagnostics_report,
    write_baseline_market_diagnostics_report,
)
from icewine_prediction.baseline_total_goals_model_service import (
    BaselineTotalGoalsModelReport,
    build_baseline_total_goals_model_report,
    write_baseline_total_goals_model_report,
)
from icewine_prediction.close_market_baseline_service import (
    build_close_market_baseline_report_from_session,
    format_close_market_baseline_report,
)
from icewine_prediction.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from icewine_prediction.dixon_coles_model_service import (
    DixonColesAttackDefenseModel,
    DixonColesGoalModel,
    train_dixon_coles_attack_defense_model,
    train_dixon_coles_goal_model,
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
from icewine_prediction.historical_odds_audit_service import (
    audit_live_historical_odds,
    clear_historical_odds_for_leagues,
    clear_historical_odds_snapshots,
    delete_live_historical_odds,
)
from icewine_prediction.historical_odds_feature_service import (
    HistoricalOddsMarketFeature,
    list_historical_odds_market_features,
)
from icewine_prediction.historical_odds_service import (
    supplement_historical_odds_snapshots_from_raw,
)
from icewine_prediction.historical_odds_anchor_coverage_service import (
    HistoricalOddsAnchorCoverageReport,
    build_historical_odds_anchor_coverage_report,
    write_historical_odds_anchor_coverage_report,
)
from icewine_prediction.historical_training_sample_service import (
    DEFAULT_ANCHORS,
    HistoricalMarketTrainingSample,
    list_historical_market_training_samples,
)
from icewine_prediction.historical_training_sample_report_service import (
    DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START,
    build_historical_odds_sample_quality_report,
    format_historical_odds_sample_quality_report,
)
from icewine_prediction.match_query_service import list_upcoming_matches
from icewine_prediction.model_training_service import (
    BaselineResultEvaluation,
    evaluate_baseline_result_model,
    train_league_team_strength_goal_model,
)
from icewine_prediction.negative_binomial_model_service import (
    NegativeBinomialTotalGoalsModel,
    train_negative_binomial_total_goals_model,
)
from icewine_prediction.oddspapi_batch_backfill_service import (
    build_oddspapi_sample_candidate_report,
    run_oddspapi_batch_backfill,
    run_oddspapi_batch_worker,
)
from icewine_prediction.oddspapi_backfill_audit_service import (
    build_oddspapi_backfill_audit,
)
from icewine_prediction.oddspapi_alias_suggestion_service import (
    build_oddspapi_alias_suggestions_text,
)
from icewine_prediction.oddspapi_diagnostic_service import (
    run_oddspapi_fixture_diagnostics,
)
from icewine_prediction.oddspapi_sync_runner import (
    build_oddspapi_match_report,
    build_oddspapi_probe_report,
    build_oddspapi_sync_plan,
    run_oddspapi_sync,
)
from icewine_prediction.oddspapi_worker_process_service import (
    build_oddspapi_batch_worker_status,
    start_oddspapi_batch_worker_process,
)
from icewine_prediction.the_odds_api_probe_service import (
    build_the_odds_api_probe_report,
    build_the_odds_api_sports_report,
    build_the_odds_api_upcoming_coverage_report,
)
from icewine_prediction.the_odds_api_sync_runner import (
    build_the_odds_api_match_report,
    build_the_odds_api_sync_plan,
    run_the_odds_api_sync,
)
from icewine_prediction.paper_recommendation_queue_service import (
    DEFAULT_FEATURE_CSV_PATH,
    PaperRecommendationQueueReport,
    build_paper_recommendation_queue,
    write_paper_recommendation_queue_report,
)
from icewine_prediction.paper_recommendation_replay_service import (
    build_walk_forward_replay_scorer_factory,
    replay_finished_matches_as_paper_recommendations,
)
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    backfill_group_snapshots,
    build_snapshot_report,
    format_snapshot_report,
    write_snapshot_report_csv,
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
from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.models import TrainingRun
from icewine_prediction.settings import load_project_settings
from icewine_prediction.skellam_model_service import SkellamMarginModel
from icewine_prediction.sync_runner import (
    build_api_football_provider,
    build_history_backfill_plan,
    fetch_and_store_odds_snapshots,
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
aliases_app = typer.Typer(help="外部数据源别名命令")
app.add_typer(aliases_app, name="aliases")


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


def format_historical_market_training_sample_line(
    sample: HistoricalMarketTrainingSample,
    display_service: DisplayNameService,
) -> str:
    kickoff = sample.kickoff_time.strftime("%Y-%m-%d %H:%M")
    league_name = display_service.display_league(sample.league_name)
    home_name = display_service.display_team(sample.home_team_name)
    away_name = display_service.display_team(sample.away_team_name)
    anchor_labels = "/".join(anchor.label for anchor in sample.anchors) or "-"
    missing_labels = "/".join(sample.missing_anchor_labels) or "-"
    quality_tags = "/".join(sample.quality_tags) or "-"
    odds_movement = (
        f"{sample.side_a_odds_movement if sample.side_a_odds_movement is not None else '-'}"
        f"/{sample.side_b_odds_movement if sample.side_b_odds_movement is not None else '-'}"
    )
    if sample.side_c_odds_movement is not None:
        odds_movement = f"{odds_movement}/{sample.side_c_odds_movement}"
    return (
        f"{league_name} {kickoff} {home_name} vs {away_name} | "
        f"{sample.market_type} {sample.bookmaker} | "
        f"锚点 {len(sample.anchors)}/{len(DEFAULT_ANCHORS)} {anchor_labels} | "
        f"快照 {sample.snapshot_count} | "
        f"盘口变化 {sample.line_movement if sample.line_movement is not None else '-'} | "
        f"赔率变化 {odds_movement} | "
        f"缺失 {missing_labels} | "
        f"标签 {quality_tags}"
    )


def format_historical_odds_market_feature_line(
    feature: HistoricalOddsMarketFeature,
    display_service: DisplayNameService,
) -> str:
    kickoff = feature.kickoff_time.strftime("%Y-%m-%d %H:%M")
    league_name = display_service.display_league(feature.league_name)
    home_name = display_service.display_team(feature.home_team_name)
    away_name = display_service.display_team(feature.away_team_name)
    close_probabilities = _format_probability_triplet(
        feature.close_side_a_implied_probability,
        feature.close_side_b_implied_probability,
        feature.close_side_c_implied_probability,
    )
    probability_movement = _format_probability_triplet(
        feature.side_a_implied_probability_movement,
        feature.side_b_implied_probability_movement,
        feature.side_c_implied_probability_movement,
    )
    return (
        f"{league_name} {kickoff} {home_name} vs {away_name} | "
        f"{feature.market_type} {feature.bookmaker} | "
        f"锚点 {feature.opening_anchor_label}->{feature.close_anchor_label} | "
        f"close {close_probabilities} | "
        f"prob变化 {probability_movement} | "
        f"盘口变化 {feature.line_movement if feature.line_movement is not None else '-'} | "
        f"overround {feature.opening_overround}->{feature.close_overround} | "
        f"标签 {'/'.join(feature.quality_tags) or '-'}"
    )


def _format_probability_triplet(
    first: Decimal | None,
    second: Decimal | None,
    third: Decimal | None,
) -> str:
    parts = [
        str(value) if value is not None else "-"
        for value in (first, second, third)
    ]
    if third is None:
        return "/".join(parts[:2])
    return "/".join(parts)


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


def format_baseline_training_dataset_command_result(
    *,
    dataset_path: str,
    report_path: str,
    dataset: BaselineTrainingDataset,
) -> str:
    return "\n".join(
        [
            "baseline dataset written",
            f"dataset: {dataset_path}",
            f"report: {report_path}",
            (
                f"rows {dataset.audit.complete_match_count}/{dataset.audit.eligible_match_count}"
                f" coverage {dataset.audit.coverage_ratio}"
            ),
        ]
    )


def format_baseline_training_dataset_qa_command_result(
    *,
    report_path: str,
    report: BaselineTrainingDatasetQaReport,
) -> str:
    return "\n".join(
        [
            "baseline dataset QA written",
            f"report: {report_path}",
            (
                f"rows {report.row_count}"
                f" invalid-cells "
                f"{sum(report.empty_required_cells.values()) + sum(report.invalid_odds_cells.values()) + sum(report.invalid_probability_cells.values()) + sum(report.invalid_overround_cells.values())}"
                f" thin-history {report.thin_history_count}"
            ),
        ]
    )


def format_baseline_market_baseline_command_result(
    *,
    report_path: str,
    report: BaselineTrainingDatasetMarketBaselineReport,
) -> str:
    return "\n".join(
        [
            "close-market baseline written",
            f"report: {report_path}",
            (
                f"evaluated {report.total_evaluated_market_samples}/"
                f"{report.total_market_samples}"
            ),
        ]
    )


def format_baseline_feature_set_command_result(
    *,
    output_path: str,
    report_path: str,
    feature_set: BaselineFeatureSet,
) -> str:
    return "\n".join(
        [
            "baseline feature set written",
            f"features: {output_path}",
            f"report: {report_path}",
            (
                f"rows {feature_set.report.row_count}"
                f" train {feature_set.report.train_rows}"
                f" validation {feature_set.report.validation_rows}"
            ),
        ]
    )


def format_baseline_dynamic_feature_set_command_result(
    *,
    output_path: str,
    report_path: str,
    feature_set: BaselineDynamicFeatureSet,
) -> str:
    return "\n".join(
        [
            "baseline dynamic feature set written",
            f"features: {output_path}",
            f"report: {report_path}",
            (
                f"rows {feature_set.report.row_count}"
                f" asian {feature_set.report.rows_with_asian_handicap_dynamic}"
                f" total {feature_set.report.rows_with_total_goals_dynamic}"
                f" complete-core {feature_set.report.complete_core_anchor_rows}"
            ),
        ]
    )


def format_baseline_match_winner_model_command_result(
    *,
    report_path: str,
    report: BaselineMatchWinnerModelReport,
) -> str:
    lines = [
        "baseline match winner model written",
        f"report: {report_path}",
        f"rows {report.row_count} train {report.train_rows} validation {report.validation_rows}",
    ]
    lines.extend(
        f"{name} log-loss {model_report.log_loss} accuracy {model_report.accuracy}"
        for name, model_report in report.model_reports.items()
    )
    return "\n".join(lines)


def format_baseline_asian_handicap_model_command_result(
    *,
    report_path: str,
    report: BaselineAsianHandicapModelReport,
) -> str:
    lines = [
        "baseline asian handicap model written",
        f"report: {report_path}",
        (
            f"rows {report.row_count} train {report.train_rows} "
            f"validation {report.validation_rows} skipped {report.skipped_rows}"
        ),
    ]
    lines.extend(
        f"{name} log-loss {model_report.log_loss} accuracy {model_report.accuracy}"
        for name, model_report in report.model_reports.items()
    )
    return "\n".join(lines)


def format_baseline_total_goals_model_command_result(
    *,
    report_path: str,
    report: BaselineTotalGoalsModelReport,
) -> str:
    lines = [
        "baseline total goals model written",
        f"report: {report_path}",
        (
            f"rows {report.row_count} train {report.train_rows} "
            f"validation {report.validation_rows} skipped {report.skipped_rows}"
        ),
    ]
    lines.extend(
        f"{name} log-loss {model_report.log_loss} accuracy {model_report.accuracy}"
        for name, model_report in report.model_reports.items()
    )
    return "\n".join(lines)


def format_baseline_edge_backtest_command_result(
    *,
    report_path: str,
    report: BaselineEdgeBacktestReport,
) -> str:
    lines = [
        "baseline edge backtest written",
        f"report: {report_path}",
        f"rows {report.row_count}",
    ]
    for market_name, market_report in report.market_reports.items():
        for model_name, model_report in market_report.model_reports.items():
            first_bucket = model_report.threshold_buckets[0]
            lines.append(
                f"{market_name} {model_name} bets {first_bucket.bet_count} "
                f"roi {first_bucket.roi if first_bucket.roi is not None else '-'}"
            )
    return "\n".join(lines)


def format_baseline_walk_forward_edge_command_result(
    *,
    report_path: str,
    report: BaselineWalkForwardEdgeReport,
) -> str:
    lines = [
        "baseline walk-forward edge backtest written",
        f"report: {report_path}",
        f"rows {report.row_count} folds {report.fold_count}",
    ]
    for market_name, market_report in report.market_reports.items():
        for model_name, model_report in market_report.model_reports.items():
            first_summary = model_report.threshold_summaries[0]
            lines.append(
                f"{market_name} {model_name} threshold {first_summary.threshold} "
                f"positive {first_summary.positive_roi_folds}/{first_summary.fold_count} "
                f"avg-roi {first_summary.average_roi if first_summary.average_roi is not None else '-'}"
            )
    return "\n".join(lines)


def format_baseline_recommendation_sandbox_command_result(
    *,
    report_path: str,
    report: BaselineRecommendationSandboxReport,
) -> str:
    lines = [
        "baseline recommendation sandbox written",
        f"report: {report_path}",
        (
            f"{report.market_type} {report.model_name} "
            f"candidates {report.total_candidates} "
            f"displayed {len(report.displayed_candidates)}"
        ),
    ]
    for summary in report.side_summaries:
        lines.append(
            f"side {summary.name} bets {summary.candidate_count} "
            f"roi {summary.roi}"
        )
    return "\n".join(lines)


def format_baseline_walk_forward_sandbox_command_result(
    *,
    report_path: str,
    report: BaselineWalkForwardSandboxReport,
) -> str:
    lines = [
        "baseline walk-forward recommendation sandbox written",
        f"report: {report_path}",
        (
            f"{report.market_type} {report.model_name} "
            f"folds {report.fold_count} candidates {report.total_candidates} "
            f"positive {report.positive_roi_folds}/{report.fold_count}"
        ),
    ]
    for summary in report.side_summaries:
        lines.append(
            f"side {summary.name} bets {summary.candidate_count} "
            f"positive {summary.positive_roi_folds} roi "
            f"{summary.roi if summary.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_away_cover_stability_command_result(
    *,
    report_path: str,
    report: BaselineAwayCoverStabilityReport,
) -> str:
    lines = [
        "baseline away-cover stability written",
        f"report: {report_path}",
        (
            f"{report.market_type} {report.model_name} {report.side} "
            f"thresholds {len(report.threshold_summaries)}"
        ),
    ]
    if report.threshold_summaries:
        summary = report.threshold_summaries[0]
        lines.append(
            f"first-threshold {summary.threshold} bets {summary.candidate_count} "
            f"positive {summary.positive_roi_folds}/{report.fold_count} "
            f"roi {summary.roi if summary.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_away_cover_bucket_threshold_command_result(
    *,
    report_path: str,
    report: BaselineAwayCoverBucketThresholdReport,
) -> str:
    lines = [
        "baseline away-cover bucket threshold written",
        f"report: {report_path}",
        (
            f"{report.market_type} {report.model_name} {report.side} "
            f"buckets {len(report.selected_thresholds)}"
        ),
    ]
    for selection in report.selected_thresholds:
        lines.append(
            f"{selection.line_bucket} threshold {selection.threshold} "
            f"bets {selection.candidate_count} roi {selection.roi if selection.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_away_cover_bucket_sandbox_command_result(
    *,
    report_path: str,
    report: BaselineAwayCoverBucketSandboxReport,
) -> str:
    lines = [
        "baseline away-cover bucket sandbox written",
        f"report: {report_path}",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} bets {summary.candidate_count} "
            f"positive {summary.positive_roi_folds}/{report.fold_count} "
            f"roi {summary.roi if summary.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_total_goals_edge_stability_command_result(
    *,
    report_path: str,
    report: BaselineTotalGoalsEdgeStabilityReport,
) -> str:
    lines = [
        "baseline total-goals edge stability written",
        f"report: {report_path}",
        f"{report.market_type} {report.model_name} thresholds {len(report.threshold_summaries)}",
    ]
    if report.threshold_summaries:
        summary = report.threshold_summaries[0]
        lines.append(
            f"first-threshold {summary.threshold} bets {summary.candidate_count} "
            f"positive {summary.positive_roi_folds}/{report.fold_count} "
            f"roi {summary.roi if summary.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_total_goals_bucket_sandbox_command_result(
    *,
    report_path: str,
    report: BaselineTotalGoalsBucketSandboxReport,
) -> str:
    lines = [
        "baseline total-goals bucket sandbox written",
        f"report: {report_path}",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} bets {summary.candidate_count} "
            f"positive {summary.positive_roi_folds}/{report.fold_count} "
            f"roi {summary.roi if summary.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_total_goals_v3_signal_research_command_result(
    *,
    report_path: str,
    report: BaselineTotalGoalsV3SignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "baseline total-goals v3 signal research written",
        f"report: {report_path}",
        (
            f"promotable {rating_counts['promotable']} "
            f"watchlist {rating_counts['watchlist']} rejected {rating_counts['rejected']}"
        ),
    ]
    if report.candidate_summaries:
        top = report.candidate_summaries[0]
        lines.append(
            f"top {top.side_bucket} threshold {top.threshold} "
            f"roi {top.roi if top.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_home_cover_signal_research_command_result(
    *,
    report_path: str,
    report: BaselineHomeCoverSignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "baseline home-cover signal research written",
        f"report: {report_path}",
        (
            f"promotable {rating_counts['promotable']} "
            f"watchlist {rating_counts['watchlist']} rejected {rating_counts['rejected']}"
        ),
    ]
    if report.candidate_summaries:
        top = report.candidate_summaries[0]
        lines.append(
            f"top {top.line_bucket} threshold {top.threshold} "
            f"roi {top.roi if top.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_model_consensus_signal_research_command_result(
    *,
    report_path: str,
    report: BaselineModelConsensusSignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "baseline model-consensus signal research written",
        f"report: {report_path}",
        (
            f"promotable {rating_counts['promotable']} "
            f"watchlist {rating_counts['watchlist']} rejected {rating_counts['rejected']}"
        ),
    ]
    if report.candidate_summaries:
        top = report.candidate_summaries[0]
        lines.append(
            f"top {top.signal_bucket} threshold {top.threshold} "
            f"roi {top.roi if top.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_t15_signal_comparison_command_result(
    *,
    report_path: str,
    report: BaselineT15SignalComparisonReport,
) -> str:
    lines = [
        "baseline T-15 signal comparison written",
        f"report: {report_path}",
        (
            f"validation {report.validation_rows} "
            f"t15_available {report.t15_available_rows} missing {report.missing_t15_rows}"
        ),
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} close {summary.close_count} "
            f"t15 {summary.t15_count} overlap {summary.overlap_count} "
            f"close_roi {summary.close_roi if summary.close_roi is not None else '-'} "
            f"t15_roi {summary.t15_roi if summary.t15_roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_execution_robustness_command_result(
    *,
    report_path: str,
    report: BaselineExecutionRobustnessReport,
) -> str:
    lines = [
        "baseline execution robustness written",
        f"report: {report_path}",
        (
            f"validation {report.validation_rows} "
            f"primary T-{report.primary_target} "
            f"targets {','.join(str(target) for target in report.execution_targets)} "
            f"latest_available {report.latest_available_rows}"
        ),
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} primary {summary.primary_count} "
            f"strong {summary.level_counts['strong']} "
            f"candidate {summary.level_counts['candidate']} "
            f"watch {summary.level_counts['watch']} "
            f"rejected {summary.level_counts['rejected']}"
        )
    return "\n".join(lines)


def format_baseline_execution_robustness_grid_command_result(
    *,
    report_path: str,
    report: BaselineExecutionRobustnessGridReport,
) -> str:
    lines = [
        "baseline execution robustness grid written",
        f"report: {report_path}",
        (
            f"validation {report.validation_rows} "
            f"primary_targets {','.join(str(target) for target in report.primary_targets)} "
            f"grid_rows {len(report.grid_rows)}"
        ),
    ]
    for row in report.top_rows[:10]:
        lines.append(
            f"{row.strategy_key} T-{row.primary_target} "
            f"seen>={row.min_seen_count} edge>={row.min_edge} "
            f"bets {row.candidate_count} roi {row.roi if row.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_execution_robustness_filter_command_result(
    *,
    report_path: str,
    report: BaselineExecutionRobustnessFilterReport,
) -> str:
    lines = [
        "baseline execution robustness filter written",
        f"report: {report_path}",
        (
            f"validation {report.validation_rows} "
            f"primary_targets {','.join(str(target) for target in report.primary_targets)} "
            f"strategies {len(report.strategy_summaries)}"
        ),
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} "
            f"raw {summary.raw_count} roi {summary.raw_roi if summary.raw_roi is not None else '-'} "
            f"kept {summary.kept_count} roi {summary.kept_roi if summary.kept_roi is not None else '-'} "
            f"filtered {summary.filtered_count} roi "
            f"{summary.filtered_roi if summary.filtered_roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_baseline_paper_discovery_alignment_command_result(
    *,
    report_path: str,
    report: BaselinePaperDiscoveryAlignmentReport,
) -> str:
    lines = [
        "baseline paper discovery alignment written",
        f"report: {report_path}",
        (
            f"validation {report.validation_rows} "
            f"latest_available {report.latest_available_rows} "
            f"t15_available {report.t15_available_rows}"
        ),
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"{summary.strategy_key} "
            f"latest {summary.latest.count} roi "
            f"{summary.latest.roi if summary.latest.roi is not None else '-'} "
            f"t15 {summary.t15_primary.count} roi "
            f"{summary.t15_primary.roi if summary.t15_primary.roi is not None else '-'} "
            f"robust_not_latest {summary.robust_kept_not_latest.count} roi "
            f"{summary.robust_kept_not_latest.roi if summary.robust_kept_not_latest.roi is not None else '-'}"
        )
    return "\n".join(lines)


def format_paper_recommendation_queue_command_result(
    *,
    report_path: str,
    report: PaperRecommendationQueueReport,
) -> str:
    lines = [
        "paper recommendation queue written",
        f"report: {report_path}",
        (
            f"window {report.hours}h near-start {report.near_start_hours}h "
            f"candidates {report.candidate_count}/{report.total_matches}"
        ),
    ]
    lines.extend(
        f"status {status} {count}" for status, count in sorted(report.status_counts.items())
    )
    if report.prefetch_result is not None:
        lines.append(
            "prefetch "
            f"created {report.prefetch_result.get('created')} "
            f"skipped {report.prefetch_result.get('skipped')}"
        )
    return "\n".join(lines)


def format_baseline_market_diagnostics_command_result(
    *,
    report_path: str,
    report: BaselineMarketDiagnosticsReport,
) -> str:
    lines = [
        "baseline market diagnostics written",
        f"report: {report_path}",
        f"rows {report.row_count} validation {report.validation_rows}",
    ]
    lines.extend(
        (
            f"{name} accuracy {market_report.overall.accuracy} "
            f"rows {market_report.eligible_rows}"
        )
        for name, market_report in report.market_reports.items()
    )
    return "\n".join(lines)


def format_historical_odds_anchor_coverage_command_result(
    *,
    report_path: str,
    report: HistoricalOddsAnchorCoverageReport,
) -> str:
    lines = [
        "historical odds anchor coverage written",
        f"report: {report_path}",
        f"eligible matches {report.eligible_match_count}",
    ]
    lines.extend(
        (
            f"{name} samples {market_report.sample_count} "
            f"complete-core {market_report.complete_core_anchor_sample_count}"
        )
        for name, market_report in report.market_reports.items()
    )
    return "\n".join(lines)


def format_bookmaker_overlap_comparison_command_result(
    *,
    report_path: str,
    report: BookmakerOverlapComparisonReport,
) -> str:
    return "\n".join(
        [
            "bookmaker_overlap_comparison written",
            f"report: {report_path}",
            (
                f"baseline={report.baseline_bookmaker} "
                f"candidate={report.candidate_bookmaker}"
            ),
            (
                f"baseline_samples={report.baseline_sample_count} "
                f"candidate_samples={report.candidate_sample_count} "
                f"overlap={report.overlap_sample_count} "
                f"coverage={report.coverage_ratio}"
            ),
        ]
    )


def format_bookmaker_replay_comparison_command_result(
    *,
    report_path: str,
    report: BookmakerReplayComparisonReport,
) -> str:
    return "\n".join(
        [
            "bookmaker_replay_comparison written",
            f"report: {report_path}",
            (
                f"baseline={report.baseline_bookmaker} "
                f"candidate={report.candidate_bookmaker}"
            ),
            (
                f"overlap_matches={report.overlap_match_count} "
                f"baseline_candidates={report.baseline_candidate_count} "
                f"candidate_candidates={report.candidate_candidate_count} "
                f"overlap_candidates={report.overlap_candidate_count}"
            ),
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


def format_dixon_coles_model(model: DixonColesGoalModel, sample_count: int) -> str:
    prediction = model.predict_goal_distribution()
    return "\n".join(
        [
            f"训练样本 {sample_count}",
            f"主队期望进球 {model.home_expected_goals}",
            f"客队期望进球 {model.away_expected_goals}",
            f"rho {model.rho}",
            f"主胜 {prediction.home_win_probability}",
            f"平局 {prediction.draw_probability}",
            f"客胜 {prediction.away_win_probability}",
        ]
    )


def format_dixon_coles_attack_defense_model(
    model: DixonColesAttackDefenseModel,
    sample_count: int,
) -> str:
    return "\n".join(
        [
            f"训练样本 {sample_count}",
            f"球队数 {model.team_count}",
            f"主队基础期望进球 {model.home_base_expected_goals}",
            f"客队基础期望进球 {model.away_base_expected_goals}",
            f"主场优势 {model.home_advantage}",
            f"rho {model.rho}",
        ]
    )


def format_skellam_handicap_probability(
    model: SkellamMarginModel,
    line: Decimal,
) -> str:
    probability = model.asian_handicap_probability(line)
    return "\n".join(
        [
            f"主队期望进球 {model.home_expected_goals}",
            f"客队期望进球 {model.away_expected_goals}",
            f"盘口 {probability.line}",
            f"主队覆盖概率 {probability.home_cover_probability}",
            f"客队覆盖概率 {probability.away_cover_probability}",
        ]
    )


def format_negative_binomial_total_model(
    model: NegativeBinomialTotalGoalsModel,
    sample_count: int,
) -> str:
    return "\n".join(
        [
            f"训练样本 {sample_count}",
            f"总进球均值 {model.mean_goals}",
            f"离散度 {model.dispersion}",
        ]
    )


def format_negative_binomial_total_probability(
    model: NegativeBinomialTotalGoalsModel,
    line: Decimal,
) -> str:
    probability = model.total_goals_probability(line)
    return "\n".join(
        [
            f"总进球均值 {model.mean_goals}",
            f"离散度 {model.dispersion}",
            f"大小球盘口 {probability.line}",
            f"大球概率 {probability.over_probability}",
            f"小球概率 {probability.under_probability}",
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


@recommendations_app.command("paper-queue")
def recommendations_paper_queue(
    hours: int = typer.Option(72, "--hours"),
    near_start_hours: int = typer.Option(6, "--near-start-hours"),
    edge_threshold: str = typer.Option("0.10", "--edge-threshold"),
    prefetch_odds: bool = typer.Option(False, "--prefetch-odds/--no-prefetch-odds"),
    report_path: str = typer.Option(
        "docs/模型实验/20260530-paper-recommendation-queue-v1.md",
        "--report-path",
    ),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        provider = None

        def odds_prefetcher(fixture_ids: list[str]):
            nonlocal provider
            if provider is None:
                provider = build_api_football_provider(load_project_settings())
            return fetch_and_store_odds_snapshots(session, provider, fixture_ids)

        report = build_paper_recommendation_queue(
            session,
            now=now_beijing(),
            hours=hours,
            near_start_hours=near_start_hours,
            edge_threshold=edge_threshold,
            prefetch_odds=prefetch_odds,
            odds_prefetcher=odds_prefetcher,
            display_name_service=DisplayNameService(),
        )
    write_paper_recommendation_queue_report(report, Path(report_path))
    typer.echo(
        format_paper_recommendation_queue_command_result(
            report_path=report_path,
            report=report,
        )
    )


@recommendations_app.command("paper-replay")
def recommendations_paper_replay(
    from_time: str = typer.Option(..., "--from-time"),
    to_time: str | None = typer.Option(None, "--to-time"),
    edge_threshold: str = typer.Option("0.10", "--edge-threshold"),
    feature_csv_path: str | None = typer.Option(None, "--feature-csv-path"),
    settle: bool = typer.Option(True, "--settle/--no-settle"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        resolved_feature_path = (
            Path(feature_csv_path)
            if feature_csv_path is not None
            else _latest_successful_dynamic_feature_path(session)
        )
        resolved_feature_path = Path(resolved_feature_path)
        scorer_factory = build_walk_forward_replay_scorer_factory(resolved_feature_path)
        result = replay_finished_matches_as_paper_recommendations(
            session,
            from_time=datetime.fromisoformat(from_time),
            to_time=datetime.fromisoformat(to_time) if to_time is not None else now_beijing(),
            scorer_factory=scorer_factory,
            recorded_at=now_beijing(),
            edge_threshold=edge_threshold,
            settle=settle,
            display_name_service=DisplayNameService(),
        )
    typer.echo(
        "paper replay "
        f"scanned {result.scanned_matches} matches "
        f"candidates {result.candidate_rows} "
        f"created {result.created_records} "
        f"duplicates {result.duplicate_records} "
        f"settled {result.settled_records} "
        f"skipped {result.skipped_settlement_records} "
        f"unsettleable {result.unsettleable_records}"
    )


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


def _latest_successful_dynamic_feature_path(session) -> Path:
    run = (
        session.query(TrainingRun)
        .filter(TrainingRun.run_type == "full_refresh")
        .filter(TrainingRun.status == "success")
        .filter(TrainingRun.dynamic_feature_path.isnot(None))
        .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        .first()
    )
    if run is None or not run.dynamic_feature_path:
        raise typer.BadParameter("未找到成功训练运行的动态特征 CSV，请使用 --feature-csv-path 指定")
    return Path(run.dynamic_feature_path)


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


def _parse_cli_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if "T" in value or " " in value:
        return datetime.fromisoformat(value)
    if end_of_day:
        return datetime.fromisoformat(f"{value}T23:59:59.999999")
    return datetime.fromisoformat(f"{value}T00:00:00")


def _parse_cli_datetime_start(value: str | None) -> datetime | None:
    return _parse_cli_datetime(value, end_of_day=False)


def _parse_cli_datetime_end(value: str | None) -> datetime | None:
    return _parse_cli_datetime(value, end_of_day=True)


@records_app.command("snapshots-backfill")
def records_snapshots_backfill(
    from_date: str = typer.Option(
        ...,
        "--from-date",
        help="Inclusive match kickoff_time start date or datetime.",
    ),
    to_date: str = typer.Option(
        ...,
        "--to-date",
        help="Inclusive match kickoff_time end date or datetime.",
    ),
    source: str = typer.Option("historical_backfill", "--source"),
    version: str = typer.Option("paper_confidence_v1", "--version"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = backfill_group_snapshots(
            session,
            from_date=_parse_cli_datetime_start(from_date),
            to_date=_parse_cli_datetime_end(to_date),
            created_at=datetime.now(tz=ZoneInfo("Asia/Shanghai")),
            snapshot_source=source,
            snapshot_version=version,
            dry_run=dry_run,
        )
    typer.echo(
        "snapshot backfill "
        f"created={result.created_count} "
        f"candidate_groups={result.candidate_group_count} "
        f"skipped={result.skipped_count} "
        f"dry_run={result.dry_run}"
    )


@records_app.command("snapshot-report")
def records_snapshot_report(
    from_date: str | None = typer.Option(
        None,
        "--from-date",
        help="Inclusive representative match kickoff_time start date or datetime.",
    ),
    to_date: str | None = typer.Option(
        None,
        "--to-date",
        help="Inclusive representative match kickoff_time end date or datetime.",
    ),
    version: str = typer.Option("paper_confidence_v1", "--version"),
    source: str | None = typer.Option(None, "--source"),
    csv_path: str | None = typer.Option(None, "--csv-path"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_snapshot_report(
            session,
            from_date=_parse_cli_datetime_start(from_date),
            to_date=_parse_cli_datetime_end(to_date),
            snapshot_version=version,
            snapshot_source=source,
        )
    if csv_path is not None:
        write_snapshot_report_csv(report, Path(csv_path))
    typer.echo(format_snapshot_report(report))
    if csv_path is not None:
        typer.echo(f"CSV written: {csv_path}")


@odds_source_app.command("oddspapi-plan")
def odds_source_oddspapi_plan(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
):
    typer.echo(
        build_oddspapi_sync_plan(
            season=season,
            max_matches=max_matches,
            league_ids=_parse_str_set(league_ids),
            from_date=date.fromisoformat(from_date) if from_date else None,
        )
    )


@odds_source_app.command("oddspapi-fetch")
def odds_source_oddspapi_fetch(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
    request_budget: int = typer.Option(50, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    max_snapshots_per_match: int = typer.Option(300, "--max-snapshots-per-match"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    historical_odds_cooldown_seconds: float = typer.Option(
        6,
        "--historical-odds-cooldown-seconds",
    ),
    refresh_pre_kickoff_existing: bool = typer.Option(False, "--refresh-pre-kickoff-existing"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    typer.echo(
        run_oddspapi_sync(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            skip_match_ids=_parse_id_set(skip_match_ids),
            match_ids=_parse_id_set(match_ids),
            league_ids=_parse_str_set(league_ids),
            from_date=date.fromisoformat(from_date) if from_date else None,
            historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
            refresh_pre_kickoff_existing=refresh_pre_kickoff_existing,
            bookmaker=bookmaker,
            progress_callback=typer.echo,
        )
    )


@odds_source_app.command("oddspapi-batch-backfill")
def odds_source_oddspapi_batch_backfill(
    season: int = typer.Option(..., "--season"),
    mode: str = typer.Option("balanced", "--mode"),
    chunk_size: int = typer.Option(20, "--chunk-size"),
    request_budget_per_league: int = typer.Option(800, "--request-budget-per-league"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    max_snapshots_per_match: int = typer.Option(151, "--max-snapshots-per-match"),
    max_rounds_per_league: int = typer.Option(20, "--max-rounds-per-league"),
    stop_after_empty_matches: int = typer.Option(8, "--stop-after-empty-matches"),
    stop_after_failed_rounds: int = typer.Option(2, "--stop-after-failed-rounds"),
    round_timeout_seconds: float = typer.Option(90, "--round-timeout-seconds"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
):
    typer.echo(
        run_oddspapi_batch_backfill(
            season=season,
            mode=mode,
            chunk_size=chunk_size,
            request_budget_per_league=request_budget_per_league,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            max_rounds_per_league=max_rounds_per_league,
            stop_after_empty_matches=stop_after_empty_matches,
            stop_after_failed_rounds=stop_after_failed_rounds,
            round_timeout_seconds=round_timeout_seconds,
            bookmaker=bookmaker,
            league_ids=_parse_str_set(league_ids),
            from_date=date.fromisoformat(from_date) if from_date else None,
            skip_match_ids=_parse_id_set(skip_match_ids),
            match_ids=_parse_id_set(match_ids),
        )
    )


@odds_source_app.command("oddspapi-batch-worker")
def odds_source_oddspapi_batch_worker(
    season: int = typer.Option(..., "--season"),
    mode: str = typer.Option("balanced", "--mode"),
    chunk_size: int = typer.Option(10, "--chunk-size"),
    request_budget_per_league: int = typer.Option(500, "--request-budget-per-league"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    max_snapshots_per_match: int = typer.Option(151, "--max-snapshots-per-match"),
    max_rounds_per_league: int = typer.Option(2, "--max-rounds-per-league"),
    stop_after_empty_matches: int = typer.Option(8, "--stop-after-empty-matches"),
    stop_after_failed_rounds: int = typer.Option(2, "--stop-after-failed-rounds"),
    round_timeout_seconds: float = typer.Option(90, "--round-timeout-seconds"),
    historical_odds_cooldown_seconds: float = typer.Option(
        6,
        "--historical-odds-cooldown-seconds",
    ),
    hard_timeout_seconds: float = typer.Option(0, "--hard-timeout-seconds"),
    log_dir: str = typer.Option("logs/odds", "--log-dir"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    notify_on_complete: bool = typer.Option(False, "--notify-on-complete"),
):
    typer.echo(
        run_oddspapi_batch_worker(
            season=season,
            mode=mode,
            chunk_size=chunk_size,
            request_budget_per_league=request_budget_per_league,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            max_rounds_per_league=max_rounds_per_league,
            stop_after_empty_matches=stop_after_empty_matches,
            stop_after_failed_rounds=stop_after_failed_rounds,
            round_timeout_seconds=round_timeout_seconds,
            historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
            hard_timeout_seconds=hard_timeout_seconds,
            log_dir=log_dir,
            bookmaker=bookmaker,
            league_ids=_parse_str_set(league_ids),
            from_date=date.fromisoformat(from_date) if from_date else None,
            skip_match_ids=_parse_id_set(skip_match_ids),
            match_ids=_parse_id_set(match_ids),
            notify_on_complete=notify_on_complete,
            output_callback=typer.echo,
        )
    )


@odds_source_app.command("oddspapi-worker-start")
def odds_source_oddspapi_worker_start(
    season: int = typer.Option(..., "--season"),
    mode: str = typer.Option("balanced", "--mode"),
    chunk_size: int = typer.Option(10, "--chunk-size"),
    request_budget_per_league: int = typer.Option(500, "--request-budget-per-league"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    max_snapshots_per_match: int = typer.Option(151, "--max-snapshots-per-match"),
    max_rounds_per_league: int = typer.Option(2, "--max-rounds-per-league"),
    stop_after_empty_matches: int = typer.Option(8, "--stop-after-empty-matches"),
    stop_after_failed_rounds: int = typer.Option(2, "--stop-after-failed-rounds"),
    round_timeout_seconds: float = typer.Option(90, "--round-timeout-seconds"),
    historical_odds_cooldown_seconds: float = typer.Option(
        6,
        "--historical-odds-cooldown-seconds",
    ),
    hard_timeout_seconds: float = typer.Option(0, "--hard-timeout-seconds"),
    log_dir: str = typer.Option("logs/odds", "--log-dir"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    notify_on_complete: bool = typer.Option(False, "--notify-on-complete"),
):
    result = start_oddspapi_batch_worker_process(
        season=season,
        mode=mode,
        chunk_size=chunk_size,
        request_budget_per_league=request_budget_per_league,
        timeout_seconds=timeout_seconds,
        max_snapshots_per_match=max_snapshots_per_match,
        max_rounds_per_league=max_rounds_per_league,
        stop_after_empty_matches=stop_after_empty_matches,
        stop_after_failed_rounds=stop_after_failed_rounds,
        round_timeout_seconds=round_timeout_seconds,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        hard_timeout_seconds=hard_timeout_seconds,
        log_dir=log_dir,
        bookmaker=bookmaker,
        league_ids=_parse_str_set(league_ids),
        from_date=from_date,
        skip_match_ids=_parse_id_set(skip_match_ids),
        match_ids=_parse_id_set(match_ids),
        notify_on_complete=notify_on_complete,
    )
    typer.echo(result.to_text())


@odds_source_app.command("oddspapi-sample-candidates")
def odds_source_oddspapi_sample_candidates(
    season: int | None = typer.Option(None, "--season"),
    league_ids: str = typer.Option(..., "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    per_league: int = typer.Option(8, "--per-league"),
):
    typer.echo(
        build_oddspapi_sample_candidate_report(
            season=season,
            league_ids=_parse_str_set(league_ids) or set(),
            from_date=date.fromisoformat(from_date) if from_date else None,
            per_league=per_league,
        )
    )


@odds_source_app.command("oddspapi-worker-status")
def odds_source_oddspapi_worker_status(
    log_dir: str = typer.Option("logs/odds", "--log-dir"),
    tail_lines: int = typer.Option(30, "--tail-lines"),
):
    typer.echo(
        build_oddspapi_batch_worker_status(
            log_dir=log_dir,
            tail_lines=tail_lines,
        )
    )


@odds_source_app.command("oddspapi-probe")
def odds_source_oddspapi_probe(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(20, "--max-matches"),
    request_budget: int = typer.Option(50, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    skip_match_ids: str = typer.Option("", "--skip-match-ids"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    typer.echo(
        build_oddspapi_probe_report(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            skip_match_ids=_parse_id_set(skip_match_ids),
            bookmaker=bookmaker,
        )
    )


@odds_source_app.command("oddspapi-diagnose-fixtures")
def odds_source_oddspapi_diagnose_fixtures(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(50, "--max-matches"),
    request_budget: int = typer.Option(100, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    log_dir: str = typer.Option("logs/odds-diagnostics", "--log-dir"),
    league_ids: str = typer.Option("", "--league-ids"),
    from_date: str | None = typer.Option(None, "--from-date"),
    confidence_threshold: str = typer.Option("0.75", "--confidence-threshold"),
):
    typer.echo(
        run_oddspapi_fixture_diagnostics(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            log_dir=log_dir,
            league_ids=_parse_str_set(league_ids),
            from_date=date.fromisoformat(from_date) if from_date else None,
            confidence_threshold=confidence_threshold,
        )
    )


@odds_source_app.command("oddspapi-audit-backfill")
def odds_source_oddspapi_audit_backfill(
    season: int = typer.Option(..., "--season"),
    log_dir: str = typer.Option("logs/odds", "--log-dir"),
    top_errors: int = typer.Option(5, "--top-errors"),
):
    typer.echo(
        build_oddspapi_backfill_audit(
            season=season,
            log_dir=log_dir,
            top_errors=top_errors,
        )
    )


@odds_source_app.command("oddspapi-suggest-aliases")
def odds_source_oddspapi_suggest_aliases(
    report_dir: str = typer.Option(..., "--report-dir"),
    alias_config_path: str = typer.Option(
        "config/external_aliases.yaml",
        "--alias-config-path",
    ),
    alias_threshold: str = typer.Option("0.75", "--alias-threshold"),
    anchor_threshold: str = typer.Option("0.75", "--anchor-threshold"),
):
    typer.echo(
        build_oddspapi_alias_suggestions_text(
            report_dir=report_dir,
            alias_config_path=alias_config_path,
            alias_threshold=alias_threshold,
            anchor_threshold=anchor_threshold,
        )
    )


@odds_source_app.command("oddspapi-audit-live")
def odds_source_oddspapi_audit_live():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = audit_live_historical_odds(session)
    typer.echo(f"赛中历史赔率比赛 {report.match_count}")
    typer.echo(f"赛中历史赔率快照 {report.snapshot_count}")


@odds_source_app.command("oddspapi-clear-live")
def odds_source_oddspapi_clear_live():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        deleted = delete_live_historical_odds(session)
    typer.echo(f"已删除赛中历史赔率快照 {deleted}")


@odds_source_app.command("oddspapi-clear-snapshots")
def odds_source_oddspapi_clear_snapshots():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        deleted = clear_historical_odds_snapshots(session, source_name="oddspapi")
    typer.echo(f"已删除 OddsPapi 历史赔率快照 {deleted}")


@odds_source_app.command("oddspapi-clear-league-snapshots")
def odds_source_oddspapi_clear_league_snapshots(
    league_ids: str = typer.Option(..., "--league-ids"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = clear_historical_odds_for_leagues(
            session,
            source_name="oddspapi",
            league_ids=_parse_str_set(league_ids) or set(),
        )
    typer.echo(f"已删除 OddsPapi 主表历史赔率快照 {report.main_snapshot_count}")
    typer.echo(f"已删除 OddsPapi raw 历史赔率快照 {report.raw_snapshot_count}")
    typer.echo(f"已重置 OddsPapi 比赛历史赔率状态 {report.reset_source_match_count}")


@odds_source_app.command("oddspapi-supplement-snapshots-from-raw")
def odds_source_oddspapi_supplement_snapshots_from_raw(
    match_ids: str = typer.Option("", "--match-ids"),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = supplement_historical_odds_snapshots_from_raw(
            session,
            match_ids=_parse_id_set(match_ids) if match_ids.strip() else None,
            source_name=source_name,
            bookmaker=bookmaker,
        )
    typer.echo(
        "raw_supplement "
        f"scanned={report.scanned_match_count} "
        f"skipped_no_raw={report.skipped_no_raw_count} "
        f"supplemented_matches={report.supplemented_match_count} "
        f"added_groups={report.added_group_count} "
        f"added_snapshots={report.added_snapshot_count}"
    )


@odds_source_app.command("oddspapi-match-report")
def odds_source_oddspapi_match_report(match_id: int = typer.Option(..., "--match-id")):
    typer.echo(build_oddspapi_match_report(match_id=match_id))


@odds_source_app.command("the-odds-api-plan")
def odds_source_the_odds_api_plan(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(10, "--max-matches"),
    league_ids: str = typer.Option("", "--league-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    from_date: datetime | None = typer.Option(None, "--from-date"),
):
    typer.echo(
        build_the_odds_api_sync_plan(
            season=season,
            max_matches=max_matches,
            league_ids=_parse_str_set(league_ids) or None,
            match_ids=_parse_id_set(match_ids) or None,
            from_date=from_date,
        )
    )


@odds_source_app.command("the-odds-api-fetch")
def odds_source_the_odds_api_fetch(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(10, "--max-matches"),
    request_budget: int = typer.Option(20, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    league_ids: str = typer.Option("", "--league-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    from_date: datetime | None = typer.Option(None, "--from-date"),
    refresh_existing: bool = typer.Option(False, "--refresh-existing"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    region: str = typer.Option("eu", "--region"),
):
    typer.echo(
        run_the_odds_api_sync(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            league_ids=_parse_str_set(league_ids) or None,
            match_ids=_parse_id_set(match_ids) or None,
            from_date=from_date,
            refresh_existing=refresh_existing,
            bookmaker=bookmaker,
            region=region,
        )
    )


@odds_source_app.command("the-odds-api-match-report")
def odds_source_the_odds_api_match_report(match_id: int = typer.Option(..., "--match-id")):
    typer.echo(build_the_odds_api_match_report(match_id=match_id))


@odds_source_app.command("the-odds-api-probe")
def odds_source_the_odds_api_probe(
    sport_key: str = typer.Option(..., "--sport-key"),
    max_events: int = typer.Option(10, "--max-events"),
    request_budget: int = typer.Option(5, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    region: str = typer.Option("eu", "--region"),
):
    typer.echo(
        build_the_odds_api_probe_report(
            sport_key=sport_key,
            max_events=max_events,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            bookmaker=bookmaker,
            region=region,
        )
    )


@odds_source_app.command("the-odds-api-sports")
def odds_source_the_odds_api_sports(
    key_prefix: str = typer.Option("soccer_", "--key-prefix"),
    request_budget: int = typer.Option(2, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
):
    typer.echo(
        build_the_odds_api_sports_report(
            key_prefix=key_prefix,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
        )
    )


@odds_source_app.command("the-odds-api-upcoming-coverage")
def odds_source_the_odds_api_upcoming_coverage(
    sport_keys: str = typer.Option(..., "--sport-keys"),
    max_events_per_sport: int = typer.Option(10, "--max-events-per-sport"),
    request_budget: int = typer.Option(30, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    region: str = typer.Option("eu", "--region"),
):
    typer.echo(
        build_the_odds_api_upcoming_coverage_report(
            sport_keys=tuple(sorted(_parse_str_set(sport_keys) or set())),
            max_events_per_sport=max_events_per_sport,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            bookmaker=bookmaker,
            region=region,
        )
    )


def _parse_id_set(value: str) -> set[int]:
    if not value.strip():
        return set()
    return {int(item.strip()) for item in value.split(",") if item.strip()}


def _parse_str_set(value: str) -> set[str] | None:
    if not value.strip():
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def _parse_threshold_map(value: str) -> dict[str, str]:
    thresholds: dict[str, str] = {}
    for item in value.split(","):
        text = item.strip()
        if not text:
            continue
        key, separator, threshold = text.partition("=")
        if not separator or not key.strip() or not threshold.strip():
            raise typer.BadParameter("threshold map items must use key=value")
        thresholds[key.strip()] = threshold.strip()
    return thresholds


def _parse_beijing_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("expected ISO date or datetime") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE))
    return parsed.astimezone(ZoneInfo(BEIJING_TIMEZONE))


@aliases_app.command("add")
def aliases_add(
    entity_type: str = typer.Option("team", "--entity-type"),
    source_name: str = typer.Option(..., "--source-name"),
    canonical_name: str = typer.Option(..., "--canonical-name"),
    alias_name: str = typer.Option(..., "--alias-name"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        alias = add_external_alias(
            session,
            entity_type=entity_type,
            source_name=source_name,
            canonical_name=canonical_name,
            alias_name=alias_name,
        )
    typer.echo(
        f"已保存别名 #{alias.id} {alias.entity_type} {alias.source_name}: "
        f"{alias.canonical_name} = {alias.alias_name}"
    )


@aliases_app.command("list")
def aliases_list(
    entity_type: str | None = typer.Option(None, "--entity-type"),
    source_name: str | None = typer.Option(None, "--source-name"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        aliases = list_external_aliases(
            session,
            source_name=source_name,
            entity_type=entity_type,
        )
    if not aliases:
        typer.echo("暂无别名")
        return
    for alias in aliases:
        typer.echo(
            f"#{alias.id} {alias.entity_type} {alias.source_name}: "
            f"{alias.canonical_name} = {alias.alias_name}"
        )


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


@samples_app.command("historical-odds-preview")
def samples_historical_odds_preview(
    season: int | None = typer.Option(None, "--season"),
    limit: int = typer.Option(20, "--limit"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        samples = list_historical_market_training_samples(
            session,
            season=season,
            limit=limit,
            bookmaker=bookmaker,
        )
        if not samples:
            typer.echo("暂无历史赔率训练样本")
            return
        for sample in samples:
            typer.echo(format_historical_market_training_sample_line(sample, display_service))


@samples_app.command("historical-odds-report")
def samples_historical_odds_report(
    season: int | None = typer.Option(None, "--season"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    eligible_start: str = typer.Option(
        DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START.strftime("%Y-%m-%d"),
        "--eligible-start",
    ),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_historical_odds_sample_quality_report(
            session,
            season=season,
            eligible_start=_parse_beijing_datetime(eligible_start),
            bookmaker=bookmaker,
        )
        typer.echo(format_historical_odds_sample_quality_report(report))


@samples_app.command("historical-odds-anchor-coverage")
def samples_historical_odds_anchor_coverage(
    season: int | None = typer.Option(None, "--season"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    eligible_start: str = typer.Option(
        DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START.strftime("%Y-%m-%d"),
        "--eligible-start",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-historical-odds-anchor-coverage-v1.md",
        "--report-path",
    ),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_historical_odds_anchor_coverage_report(
            session,
            season=season,
            eligible_start=_parse_beijing_datetime(eligible_start),
            bookmaker=bookmaker,
        )
        write_historical_odds_anchor_coverage_report(report, Path(report_path))
        typer.echo(
            format_historical_odds_anchor_coverage_command_result(
                report_path=report_path,
                report=report,
            )
        )


@samples_app.command("historical-odds-features-preview")
def samples_historical_odds_features_preview(
    season: int | None = typer.Option(None, "--season"),
    limit: int = typer.Option(20, "--limit"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_service = DisplayNameService()
    with session_factory() as session:
        features = list_historical_odds_market_features(
            session,
            season=season,
            limit=limit,
            bookmaker=bookmaker,
        )
        if not features:
            typer.echo("暂无历史赔率特征")
            return
        for feature in features:
            typer.echo(format_historical_odds_market_feature_line(feature, display_service))


@samples_app.command("historical-odds-close-baseline")
def samples_historical_odds_close_baseline(
    season: int | None = typer.Option(None, "--season"),
    limit: int | None = typer.Option(None, "--limit"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_close_market_baseline_report_from_session(
            session,
            season=season,
            limit=limit,
            bookmaker=bookmaker,
        )
        typer.echo(format_close_market_baseline_report(report))


@samples_app.command("bookmaker-overlap-comparison")
def samples_bookmaker_overlap_comparison(
    baseline_bookmaker: str = typer.Option("pinnacle", "--baseline-bookmaker"),
    candidate_bookmaker: str = typer.Option("sbobet", "--candidate-bookmaker"),
    season: int | None = typer.Option(None, "--season"),
    limit: int | None = typer.Option(None, "--limit"),
    report_path: str = typer.Option(
        "local_data/reports/bookmaker_overlap_comparison.md",
        "--report-path",
    ),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_bookmaker_overlap_comparison_report(
            session,
            baseline_bookmaker=baseline_bookmaker,
            candidate_bookmaker=candidate_bookmaker,
            season=season,
            limit=limit,
        )
        write_bookmaker_overlap_comparison_report(report, Path(report_path))
    typer.echo(
        format_bookmaker_overlap_comparison_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("bookmaker-replay-comparison")
def samples_bookmaker_replay_comparison(
    csv_path: str = typer.Option(
        str(DEFAULT_FEATURE_CSV_PATH),
        "--csv-path",
    ),
    baseline_bookmaker: str = typer.Option("pinnacle", "--baseline-bookmaker"),
    candidate_bookmaker: str = typer.Option("sbobet", "--candidate-bookmaker"),
    edge_threshold: str = typer.Option("0.10", "--edge-threshold"),
    report_path: str = typer.Option(
        "local_data/reports/bookmaker_replay_comparison.md",
        "--report-path",
    ),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_bookmaker_replay_comparison_report(
            session,
            csv_path=Path(csv_path),
            baseline_bookmaker=baseline_bookmaker,
            candidate_bookmaker=candidate_bookmaker,
            edge_threshold=edge_threshold,
        )
        write_bookmaker_replay_comparison_report(report, Path(report_path))
    typer.echo(
        format_bookmaker_replay_comparison_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-dataset")
def samples_baseline_dataset(
    output_path: str = typer.Option(
        "local_data/training/baseline_main_leagues_20260529.csv",
        "--output-path",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-baseline-training-dataset.md",
        "--report-path",
    ),
    eligible_start: str = typer.Option(
        "2026-01-15",
        "--eligible-start",
    ),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        dataset = build_baseline_training_dataset(
            session,
            eligible_start=_parse_beijing_datetime(eligible_start),
            source_name=source_name,
            bookmaker=bookmaker,
        )
    write_baseline_training_dataset_csv(dataset, Path(output_path))
    write_baseline_training_dataset_report(dataset.audit, Path(report_path))
    typer.echo(
        format_baseline_training_dataset_command_result(
            dataset_path=output_path,
            report_path=report_path,
            dataset=dataset,
        )
    )


@samples_app.command("baseline-dataset-qa")
def samples_baseline_dataset_qa(
    csv_path: str = typer.Option(
        "local_data/training/baseline_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-baseline-training-dataset-qa.md",
        "--report-path",
    ),
    low_sample_threshold: int = typer.Option(30, "--low-sample-threshold"),
):
    report = build_baseline_training_dataset_qa_report(
        Path(csv_path),
        low_sample_threshold=low_sample_threshold,
    )
    write_baseline_training_dataset_qa_report(report, Path(report_path))
    typer.echo(
        format_baseline_training_dataset_qa_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-market-baseline")
def samples_baseline_market_baseline(
    csv_path: str = typer.Option(
        "local_data/training/baseline_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-close-market-baseline-evaluation.md",
        "--report-path",
    ),
):
    report = build_baseline_training_dataset_market_baseline_report(Path(csv_path))
    write_baseline_training_dataset_market_baseline_report(report, Path(report_path))
    typer.echo(
        format_baseline_market_baseline_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-feature-set")
def samples_baseline_feature_set(
    csv_path: str = typer.Option(
        "local_data/training/baseline_main_leagues_20260529.csv",
        "--csv-path",
    ),
    output_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--output-path",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-baseline-feature-set-v1.md",
        "--report-path",
    ),
    validation_ratio: str = typer.Option("0.20", "--validation-ratio"),
):
    feature_set = build_baseline_feature_set(
        Path(csv_path),
        validation_ratio=validation_ratio,
    )
    write_baseline_feature_set_csv(feature_set, Path(output_path))
    write_baseline_feature_set_report(feature_set.report, Path(report_path))
    typer.echo(
        format_baseline_feature_set_command_result(
            output_path=output_path,
            report_path=report_path,
            feature_set=feature_set,
        )
    )


@samples_app.command("baseline-dynamic-feature-set")
def samples_baseline_dynamic_feature_set(
    csv_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    output_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--output-path",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-baseline-dynamic-feature-set-v1.md",
        "--report-path",
    ),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        feature_set = build_baseline_dynamic_feature_set(
            session,
            Path(csv_path),
            bookmaker=bookmaker,
        )
        write_baseline_dynamic_feature_set_csv(feature_set, Path(output_path))
        write_baseline_dynamic_feature_set_report(feature_set.report, Path(report_path))
        typer.echo(
            format_baseline_dynamic_feature_set_command_result(
                output_path=output_path,
                report_path=report_path,
                feature_set=feature_set,
            )
        )


@samples_app.command("baseline-match-winner-model")
def samples_baseline_match_winner_model(
    csv_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-match-winner-model-v1.md",
        "--report-path",
    ),
):
    report = build_baseline_match_winner_model_report(Path(csv_path))
    write_baseline_match_winner_model_report(report, Path(report_path))
    typer.echo(
        format_baseline_match_winner_model_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-asian-handicap-model")
def samples_baseline_asian_handicap_model(
    csv_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-asian-handicap-model-v1.md",
        "--report-path",
    ),
):
    report = build_baseline_asian_handicap_model_report(Path(csv_path))
    write_baseline_asian_handicap_model_report(report, Path(report_path))
    typer.echo(
        format_baseline_asian_handicap_model_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-total-goals-model")
def samples_baseline_total_goals_model(
    csv_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-total-goals-model-v1.md",
        "--report-path",
    ),
):
    report = build_baseline_total_goals_model_report(Path(csv_path))
    write_baseline_total_goals_model_report(report, Path(report_path))
    typer.echo(
        format_baseline_total_goals_model_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-edge-backtest")
def samples_baseline_edge_backtest(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-edge-backtest-v1.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.00,0.02,0.04,0.06,0.08,0.10", "--thresholds"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_edge_backtest_report(Path(csv_path), thresholds=threshold_values)
    write_baseline_edge_backtest_report(report, Path(report_path))
    typer.echo(
        format_baseline_edge_backtest_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-walk-forward-edge")
def samples_baseline_walk_forward_edge(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-walk-forward-edge-v1.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.00,0.02,0.04,0.06,0.08,0.10", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_walk_forward_edge_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_walk_forward_edge_report(report, Path(report_path))
    typer.echo(
        format_baseline_walk_forward_edge_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-recommendation-sandbox")
def samples_baseline_recommendation_sandbox(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-recommendation-sandbox-v1.md",
        "--report-path",
    ),
    edge_threshold: str = typer.Option("0.10", "--edge-threshold"),
    top_n: int = typer.Option(80, "--top-n"),
):
    report = build_baseline_recommendation_sandbox_report(
        Path(csv_path),
        edge_threshold=edge_threshold,
        top_n=top_n,
    )
    write_baseline_recommendation_sandbox_report(report, Path(report_path))
    typer.echo(
        format_baseline_recommendation_sandbox_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-walk-forward-sandbox")
def samples_baseline_walk_forward_sandbox(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-walk-forward-sandbox-v1.md",
        "--report-path",
    ),
    edge_threshold: str = typer.Option("0.10", "--edge-threshold"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
    top_n_per_fold: int = typer.Option(20, "--top-n-per-fold"),
):
    report = build_baseline_walk_forward_sandbox_report(
        Path(csv_path),
        edge_threshold=edge_threshold,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
        top_n_per_fold=top_n_per_fold,
    )
    write_baseline_walk_forward_sandbox_report(report, Path(report_path))
    typer.echo(
        format_baseline_walk_forward_sandbox_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-away-cover-stability")
def samples_baseline_away_cover_stability(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-away-cover-stability-v1.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.08,0.10,0.12,0.15,0.20", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_away_cover_stability_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_away_cover_stability_report(report, Path(report_path))
    typer.echo(
        format_baseline_away_cover_stability_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-away-cover-bucket-threshold")
def samples_baseline_away_cover_bucket_threshold(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/妯″瀷瀹為獙/20260529-baseline-away-cover-bucket-threshold-v2.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.08,0.10,0.12,0.15,0.20", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_away_cover_bucket_threshold_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_away_cover_bucket_threshold_report(report, Path(report_path))
    typer.echo(
        format_baseline_away_cover_bucket_threshold_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-away-cover-bucket-sandbox")
def samples_baseline_away_cover_bucket_sandbox(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/妯″瀷瀹為獙/20260529-baseline-away-cover-bucket-sandbox-v2.md",
        "--report-path",
    ),
    v1_edge_threshold: str = typer.Option("0.10", "--v1-edge-threshold"),
    away_underdog_threshold: str = typer.Option("0.20", "--away-underdog-threshold"),
    pickem_threshold: str = typer.Option("0.08", "--pickem-threshold"),
    away_favorite_threshold: str | None = typer.Option(None, "--away-favorite-threshold"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    bucket_thresholds = {
        "away_underdog": away_underdog_threshold,
        "pickem": pickem_threshold,
    }
    if away_favorite_threshold is not None:
        bucket_thresholds["away_favorite"] = away_favorite_threshold
    report = build_baseline_away_cover_bucket_sandbox_report(
        Path(csv_path),
        v1_edge_threshold=v1_edge_threshold,
        bucket_thresholds=bucket_thresholds,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_away_cover_bucket_sandbox_report(report, Path(report_path))
    typer.echo(
        format_baseline_away_cover_bucket_sandbox_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-total-goals-edge-stability")
def samples_baseline_total_goals_edge_stability(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-total-goals-edge-stability-v1.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.08,0.10,0.12,0.15,0.20", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_total_goals_edge_stability_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_total_goals_edge_stability_report(report, Path(report_path))
    typer.echo(
        format_baseline_total_goals_edge_stability_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-total-goals-bucket-sandbox")
def samples_baseline_total_goals_bucket_sandbox(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260529-baseline-total-goals-bucket-sandbox-v2.md",
        "--report-path",
    ),
    v1_edge_threshold: str = typer.Option("0.10", "--v1-edge-threshold"),
    bucket_thresholds: str = typer.Option(
        "over@mid_2.75=0.08,under@mid_2.75=0.08",
        "--bucket-thresholds",
    ),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    report = build_baseline_total_goals_bucket_sandbox_report(
        Path(csv_path),
        v1_edge_threshold=v1_edge_threshold,
        bucket_thresholds=_parse_threshold_map(bucket_thresholds),
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_total_goals_bucket_sandbox_report(report, Path(report_path))
    typer.echo(
        format_baseline_total_goals_bucket_sandbox_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-total-goals-v3-signal-research")
def samples_baseline_total_goals_v3_signal_research(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/妯″瀷瀹為獙/20260529-baseline-total-goals-v3-signal-research.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.06,0.08,0.10,0.12,0.15,0.18,0.20", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_total_goals_v3_signal_research_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_total_goals_v3_signal_research_report(report, Path(report_path))
    typer.echo(
        format_baseline_total_goals_v3_signal_research_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-home-cover-signal-research")
def samples_baseline_home_cover_signal_research(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/妯″瀷瀹為獙/20260529-baseline-home-cover-signal-research.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.06,0.08,0.10,0.12,0.15,0.18,0.20", "--thresholds"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_home_cover_signal_research_report(
        Path(csv_path),
        thresholds=threshold_values,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_home_cover_signal_research_report(report, Path(report_path))
    typer.echo(
        format_baseline_home_cover_signal_research_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-model-consensus-signal-research")
def samples_baseline_model_consensus_signal_research(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260602-baseline-model-consensus-signal-research.md",
        "--report-path",
    ),
    thresholds: str = typer.Option("0.06,0.08,0.10,0.12,0.15,0.18,0.20", "--thresholds"),
    confirmation_threshold: str = typer.Option("0.00", "--confirmation-threshold"),
    train_ratio: str = typer.Option("0.60", "--train-ratio"),
    validation_ratio: str = typer.Option("0.10", "--validation-ratio"),
    fold_count: int = typer.Option(5, "--fold-count"),
):
    threshold_values = tuple(value.strip() for value in thresholds.split(",") if value.strip())
    report = build_baseline_model_consensus_signal_research_report(
        Path(csv_path),
        thresholds=threshold_values,
        confirmation_threshold=confirmation_threshold,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        fold_count=fold_count,
    )
    write_baseline_model_consensus_signal_research_report(report, Path(report_path))
    typer.echo(
        format_baseline_model_consensus_signal_research_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-t15-signal-comparison")
def samples_baseline_t15_signal_comparison(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260603-baseline-t15-signal-comparison.md",
        "--report-path",
    ),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    target_minutes: int = typer.Option(15, "--target-minutes"),
    tolerance_minutes: int = typer.Option(5, "--tolerance-minutes"),
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_baseline_t15_signal_comparison_report(
            session,
            Path(csv_path),
            source_name=source_name,
            bookmaker=bookmaker,
            target_minutes_before_kickoff=target_minutes,
            tolerance_minutes=tolerance_minutes,
        )
    write_baseline_t15_signal_comparison_report(report, Path(report_path))
    typer.echo(
        format_baseline_t15_signal_comparison_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-execution-robustness")
def samples_baseline_execution_robustness(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260603-baseline-execution-robustness.md",
        "--report-path",
    ),
    targets: str = typer.Option("60,30,25,20,15,10", "--targets"),
    primary_target: int = typer.Option(10, "--primary-target"),
    tolerance_minutes: int = typer.Option(5, "--tolerance-minutes"),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    execution_targets = tuple(int(value.strip()) for value in targets.split(",") if value.strip())
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_baseline_execution_robustness_report(
            session,
            Path(csv_path),
            execution_targets=execution_targets,
            primary_target=primary_target,
            tolerance_minutes=tolerance_minutes,
            source_name=source_name,
            bookmaker=bookmaker,
        )
    write_baseline_execution_robustness_report(report, Path(report_path))
    typer.echo(
        format_baseline_execution_robustness_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-execution-robustness-grid")
def samples_baseline_execution_robustness_grid(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260603-baseline-execution-robustness-grid.md",
        "--report-path",
    ),
    targets: str = typer.Option("60,30,25,20,15,10", "--targets"),
    primary_targets: str = typer.Option("10", "--primary-targets"),
    tolerance_minutes: int = typer.Option(5, "--tolerance-minutes"),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    min_candidate_count: int = typer.Option(10, "--min-candidate-count"),
    top_n_per_strategy: int = typer.Option(5, "--top-n-per-strategy"),
):
    execution_targets = tuple(int(value.strip()) for value in targets.split(",") if value.strip())
    primary_target_values = tuple(
        int(value.strip()) for value in primary_targets.split(",") if value.strip()
    )
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_baseline_execution_robustness_grid_report(
            session,
            Path(csv_path),
            execution_targets=execution_targets,
            primary_targets=primary_target_values,
            tolerance_minutes=tolerance_minutes,
            source_name=source_name,
            bookmaker=bookmaker,
            min_candidate_count=min_candidate_count,
            top_n_per_strategy=top_n_per_strategy,
        )
    write_baseline_execution_robustness_grid_report(report, Path(report_path))
    typer.echo(
        format_baseline_execution_robustness_grid_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-execution-robustness-filter")
def samples_baseline_execution_robustness_filter(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/妯″瀷瀹為獙/20260603-baseline-execution-robustness-filter.md",
        "--report-path",
    ),
    targets: str = typer.Option("60,30,25,20,15,10", "--targets"),
    tolerance_minutes: int = typer.Option(5, "--tolerance-minutes"),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    execution_targets = tuple(int(value.strip()) for value in targets.split(",") if value.strip())
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_baseline_execution_robustness_filter_report(
            session,
            Path(csv_path),
            execution_targets=execution_targets,
            tolerance_minutes=tolerance_minutes,
            source_name=source_name,
            bookmaker=bookmaker,
        )
    write_baseline_execution_robustness_filter_report(report, Path(report_path))
    typer.echo(
        format_baseline_execution_robustness_filter_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-paper-discovery-alignment")
def samples_baseline_paper_discovery_alignment(
    csv_path: str = typer.Option(
        "local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/模型实验/20260603-baseline-paper-discovery-alignment.md",
        "--report-path",
    ),
    targets: str = typer.Option("60,30,25,20,15,10", "--targets"),
    primary_target: int = typer.Option(10, "--primary-target"),
    tolerance_minutes: int = typer.Option(5, "--tolerance-minutes"),
    source_name: str = typer.Option("oddspapi", "--source-name"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
):
    execution_targets = tuple(int(value.strip()) for value in targets.split(",") if value.strip())
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_baseline_paper_discovery_alignment_report(
            session,
            Path(csv_path),
            execution_targets=execution_targets,
            primary_target=primary_target,
            tolerance_minutes=tolerance_minutes,
            source_name=source_name,
            bookmaker=bookmaker,
        )
    write_baseline_paper_discovery_alignment_report(report, Path(report_path))
    typer.echo(
        format_baseline_paper_discovery_alignment_command_result(
            report_path=report_path,
            report=report,
        )
    )


@samples_app.command("baseline-market-diagnostics")
def samples_baseline_market_diagnostics(
    csv_path: str = typer.Option(
        "local_data/training/baseline_features_main_leagues_20260529.csv",
        "--csv-path",
    ),
    report_path: str = typer.Option(
        "docs/数据审计/20260529-baseline-market-diagnostics-v1.md",
        "--report-path",
    ),
):
    report = build_baseline_market_diagnostics_report(Path(csv_path))
    write_baseline_market_diagnostics_report(report, Path(report_path))
    typer.echo(
        format_baseline_market_diagnostics_command_result(
            report_path=report_path,
            report=report,
        )
    )


@models_app.command("train-baseline")
def models_train_baseline(limit: int = typer.Option(1000, "--limit")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        evaluation = evaluate_baseline_result_model(samples)
        typer.echo(format_baseline_result_evaluation(evaluation))


@models_app.command("train-dixon-coles")
def models_train_dixon_coles(limit: int = typer.Option(1000, "--limit")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        model = train_dixon_coles_goal_model(samples)
        typer.echo(format_dixon_coles_model(model, sample_count=len(samples)))


@models_app.command("train-dixon-coles-attack-defense")
def models_train_dixon_coles_attack_defense(limit: int = typer.Option(1000, "--limit")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        model = train_dixon_coles_attack_defense_model(samples)
        typer.echo(format_dixon_coles_attack_defense_model(model, sample_count=len(samples)))


@models_app.command("skellam-handicap")
def models_skellam_handicap(
    home_expected_goals: str = typer.Option(..., "--home-eg"),
    away_expected_goals: str = typer.Option(..., "--away-eg"),
    line: str = typer.Option(..., "--line"),
):
    model = SkellamMarginModel(
        home_expected_goals=Decimal(home_expected_goals),
        away_expected_goals=Decimal(away_expected_goals),
    )
    typer.echo(format_skellam_handicap_probability(model, Decimal(line)))


@models_app.command("train-negative-binomial-total")
def models_train_negative_binomial_total(limit: int = typer.Option(1000, "--limit")):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        samples = list_training_samples(session, limit=limit)
        model = train_negative_binomial_total_goals_model(samples)
        typer.echo(format_negative_binomial_total_model(model, sample_count=len(samples)))


@models_app.command("negative-binomial-total")
def models_negative_binomial_total(
    mean_goals: str = typer.Option(..., "--mean"),
    dispersion: str = typer.Option(..., "--dispersion"),
    line: str = typer.Option(..., "--line"),
):
    model = NegativeBinomialTotalGoalsModel(
        mean_goals=Decimal(mean_goals),
        dispersion=Decimal(dispersion),
    )
    typer.echo(format_negative_binomial_total_probability(model, Decimal(line)))


if __name__ == "__main__":
    app()
