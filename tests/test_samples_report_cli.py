from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_training_sample_report
from icewine_prediction.sample_report_service import TrainingSampleReport


def test_format_training_sample_report_outputs_core_metrics():
    report = TrainingSampleReport(
        total_samples=3,
        samples_with_odds=2,
        odds_coverage_ratio=Decimal("0.67"),
        by_league={"Premier League": 2, "La Liga": 1},
        by_season={2026: 1, 2025: 2},
        by_weight={Decimal("1.00"): 1, Decimal("0.80"): 2},
    )

    text = format_training_sample_report(report)

    assert "总样本 3" in text
    assert "有赔率样本 2" in text
    assert "赔率覆盖率 0.67" in text
    assert "Premier League: 2" in text
    assert "2025: 2" in text
    assert "0.80: 2" in text


def test_samples_report_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_training_sample_report",
        lambda session: TrainingSampleReport(
            total_samples=1,
            samples_with_odds=0,
            odds_coverage_ratio=Decimal("0.00"),
            by_league={"La Liga": 1},
            by_season={2025: 1},
            by_weight={Decimal("0.80"): 1},
        ),
    )

    result = runner.invoke(app, ["samples", "report"])

    assert result.exit_code == 0
    assert "总样本 1" in result.stdout
