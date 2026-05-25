from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_baseline_result_evaluation
from icewine_prediction.dixon_coles_model_service import (
    DixonColesAttackDefenseModel,
    DixonColesGoalModel,
)
from icewine_prediction.model_training_service import BaselineResultEvaluation
from icewine_prediction.negative_binomial_model_service import NegativeBinomialTotalGoalsModel


def test_format_baseline_result_evaluation_outputs_metrics():
    evaluation = BaselineResultEvaluation(
        train_sample_count=80,
        validation_sample_count=20,
        home_expected_goals=Decimal("1.35"),
        away_expected_goals=Decimal("1.05"),
        accuracy=Decimal("0.4500"),
        average_log_loss=Decimal("1.0234"),
    )

    text = format_baseline_result_evaluation(evaluation)

    assert "训练样本 80" in text
    assert "验证样本 20" in text
    assert "主队期望进球 1.35" in text
    assert "准确率 0.4500" in text
    assert "log loss 1.0234" in text


def test_models_train_baseline_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.evaluate_baseline_result_model",
        lambda samples: BaselineResultEvaluation(
            train_sample_count=8,
            validation_sample_count=2,
            home_expected_goals=Decimal("1.20"),
            away_expected_goals=Decimal("1.00"),
            accuracy=Decimal("0.5000"),
            average_log_loss=Decimal("1.1000"),
        ),
    )

    result = runner.invoke(app, ["models", "train-baseline", "--limit", "10"])

    assert result.exit_code == 0
    assert "训练样本 8" in result.stdout


def test_models_train_dixon_coles_outputs_parameters(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_dixon_coles_goal_model",
        lambda samples: DixonColesGoalModel(
            home_expected_goals=Decimal("1.25"),
            away_expected_goals=Decimal("0.95"),
            rho=Decimal("-0.1200"),
        ),
    )

    result = runner.invoke(app, ["models", "train-dixon-coles", "--limit", "10"])

    assert result.exit_code == 0
    assert "训练样本 10" in result.stdout
    assert "主队期望进球 1.25" in result.stdout
    assert "客队期望进球 0.95" in result.stdout
    assert "rho -0.1200" in result.stdout
    assert "主胜" in result.stdout


def test_models_train_dixon_coles_attack_defense_outputs_parameters(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_dixon_coles_attack_defense_model",
        lambda samples: DixonColesAttackDefenseModel(
            home_intercept=Decimal("0.2000"),
            away_intercept=Decimal("0.0000"),
            home_advantage=Decimal("0.1800"),
            rho=Decimal("-0.0800"),
            team_parameters={},
        ),
    )

    result = runner.invoke(
        app,
        ["models", "train-dixon-coles-attack-defense", "--limit", "10"],
    )

    assert result.exit_code == 0
    assert "训练样本 10" in result.stdout
    assert "球队数 0" in result.stdout
    assert "主场优势 0.1800" in result.stdout
    assert "rho -0.0800" in result.stdout
    assert "主队基础期望进球" in result.stdout


def test_models_skellam_handicap_outputs_probabilities():
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "models",
            "skellam-handicap",
            "--home-eg",
            "1.50",
            "--away-eg",
            "1.10",
            "--line",
            "-0.25",
        ],
    )

    assert result.exit_code == 0
    assert "主队期望进球 1.50" in result.stdout
    assert "客队期望进球 1.10" in result.stdout
    assert "盘口 -0.25" in result.stdout
    assert "主队覆盖概率" in result.stdout
    assert "客队覆盖概率" in result.stdout


def test_models_train_negative_binomial_total_outputs_parameters(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_negative_binomial_total_goals_model",
        lambda samples: NegativeBinomialTotalGoalsModel(
            mean_goals=Decimal("2.60"),
            dispersion=Decimal("0.2000"),
        ),
    )

    result = runner.invoke(app, ["models", "train-negative-binomial-total", "--limit", "10"])

    assert result.exit_code == 0
    assert "训练样本 10" in result.stdout
    assert "总进球均值 2.60" in result.stdout
    assert "离散度 0.2000" in result.stdout


def test_models_negative_binomial_total_outputs_probabilities():
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "models",
            "negative-binomial-total",
            "--mean",
            "2.60",
            "--dispersion",
            "0.20",
            "--line",
            "2.75",
        ],
    )

    assert result.exit_code == 0
    assert "总进球均值 2.60" in result.stdout
    assert "离散度 0.20" in result.stdout
    assert "大小球盘口 2.75" in result.stdout
    assert "大球概率" in result.stdout
    assert "小球概率" in result.stdout
