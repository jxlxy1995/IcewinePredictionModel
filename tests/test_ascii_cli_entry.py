from typer.testing import CliRunner

from icewine_cli import app


def test_ascii_cli_entry_can_output_version():
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "冰酒足球预测模型" in result.stdout
