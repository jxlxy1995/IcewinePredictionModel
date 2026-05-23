from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app
from icewine_prediction.model_training_service import BaselineResultModel


def test_recommendations_model_preview_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_baseline_result_model",
        lambda samples: BaselineResultModel(
            home_expected_goals=Decimal("1.50"),
            away_expected_goals=Decimal("1.10"),
        ),
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.list_upcoming_match_odds_features",
        lambda session, start_time, hours: [],
    )

    result = runner.invoke(
        app,
        ["recommendations", "model-preview", "--hours", "24", "--sample-limit", "10"],
    )

    assert result.exit_code == 0
