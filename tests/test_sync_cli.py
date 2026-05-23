from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_sync_group_exposes_help():
    runner = CliRunner()

    result = runner.invoke(app, ["sync", "--help"])

    assert result.exit_code == 0
    assert "upcoming" in result.stdout
    assert "odds" in result.stdout
    assert "results" in result.stdout
