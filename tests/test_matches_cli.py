from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_matches_group_exposes_upcoming_help():
    runner = CliRunner()

    result = runner.invoke(app, ["matches", "--help"])

    assert result.exit_code == 0
    assert "upcoming" in result.stdout
