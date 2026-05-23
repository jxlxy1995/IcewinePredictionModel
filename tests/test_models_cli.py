from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_baseline_result_evaluation
from icewine_prediction.model_training_service import BaselineResultEvaluation


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
