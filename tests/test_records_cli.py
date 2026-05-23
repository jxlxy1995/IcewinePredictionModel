from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_record_report
from icewine_prediction.model_training_service import LeagueTeamStrengthGoalModel, TeamStrengthGoalModel
from icewine_prediction.record_service import RecordGroupSummary, RecordReport


def test_records_group_exposes_pending_help():
    runner = CliRunner()

    result = runner.invoke(app, ["records", "--help"])

    assert result.exit_code == 0
    assert "pending" in result.stdout


def test_recommendations_record_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_league_team_strength_goal_model",
        lambda samples: LeagueTeamStrengthGoalModel(
            global_model=TeamStrengthGoalModel(
                home_goal_average=Decimal("1.50"),
                away_goal_average=Decimal("1.10"),
                team_strengths={},
            ),
            league_models={},
        ),
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.list_upcoming_match_odds_features",
        lambda session, start_time, hours: [],
    )

    result = runner.invoke(
        app,
        ["recommendations", "record", "--hours", "24", "--sample-limit", "10"],
    )

    assert result.exit_code == 0
    assert "录入推荐 0" in result.stdout


def test_records_settle_and_report_commands_exist():
    runner = CliRunner()

    settle_result = runner.invoke(app, ["records", "settle"])
    report_result = runner.invoke(app, ["records", "report"])

    assert settle_result.exit_code == 0
    assert report_result.exit_code == 0


def test_format_record_report_outputs_summary():
    summary = RecordGroupSummary(
        record_count=2,
        stake_units=Decimal("3.00"),
        profit_units=Decimal("0.800"),
        roi=Decimal("0.2667"),
    )
    report = RecordReport(
        total_records=3,
        settled_records=2,
        pending_records=1,
        total_stake_units=Decimal("3.00"),
        total_profit_units=Decimal("0.800"),
        roi=Decimal("0.2667"),
        by_edge_bucket={"0.10+": summary},
        by_settlement_result={"win": summary},
        by_market_type={"asian_handicap": summary},
        by_confidence_grade={"A+": summary},
        by_league={"La Liga": summary},
    )

    text = format_record_report(report)

    assert "总推荐 3" in text
    assert "已结算 2" in text
    assert "待结算 1" in text
    assert "按结果" in text
    assert "win" in text
    assert "按edge" in text
    assert "0.10+" in text
    assert "总盈亏 0.800" in text
    assert "ROI 0.2667" in text
    assert "asian_handicap" in text
    assert "La Liga" in text
