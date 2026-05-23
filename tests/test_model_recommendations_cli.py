from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app
from icewine_prediction.model_training_service import TeamStrengthGoalModel


def test_recommendations_model_preview_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_training_samples",
        lambda session, limit: ["sample"] * limit,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.train_team_strength_goal_model",
        lambda samples: TeamStrengthGoalModel(
            home_goal_average=Decimal("1.50"),
            away_goal_average=Decimal("1.10"),
            team_strengths={},
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
