from typer.testing import CliRunner

from 冰酒预测.命令行 import app


def test_cli_可以输出版本():
    runner = CliRunner()

    result = runner.invoke(app, ["版本"])

    assert result.exit_code == 0
    assert "冰酒足球预测模型" in result.stdout
