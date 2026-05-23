from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_training_sample_report
from icewine_prediction.sample_report_service import LeagueTrainingSampleCoverage, TrainingSampleReport


def test_format_training_sample_report_outputs_core_metrics():
    report = TrainingSampleReport(
        total_samples=3,
        samples_with_odds=2,
        samples_with_asian_handicap=1,
        samples_with_total_goals=1,
        odds_coverage_ratio=Decimal("0.67"),
        asian_handicap_coverage_ratio=Decimal("0.33"),
        total_goals_coverage_ratio=Decimal("0.33"),
        by_league={
            "Premier League": LeagueTrainingSampleCoverage(
                total_samples=2,
                samples_with_odds=1,
                samples_with_asian_handicap=1,
                samples_with_total_goals=0,
            ),
            "La Liga": LeagueTrainingSampleCoverage(
                total_samples=1,
                samples_with_odds=1,
                samples_with_asian_handicap=0,
                samples_with_total_goals=1,
            ),
        },
        by_season={2026: 1, 2025: 2},
        by_weight={Decimal("1.00"): 1, Decimal("0.80"): 2},
    )

    text = format_training_sample_report(report)

    assert "3" in text
    assert "2" in text
    assert "1" in text
    assert "0.67" in text
    assert "0.33" in text
    assert "Premier League" in text
    assert "La Liga" in text
    assert "2025: 2" in text
    assert "0.80: 2" in text


def test_samples_report_command_exists(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_training_sample_report",
        lambda session, season=None: TrainingSampleReport(
            total_samples=1,
            samples_with_odds=0,
            samples_with_asian_handicap=0,
            samples_with_total_goals=0,
            odds_coverage_ratio=Decimal("0.00"),
            asian_handicap_coverage_ratio=Decimal("0.00"),
            total_goals_coverage_ratio=Decimal("0.00"),
            by_league={
                "La Liga": LeagueTrainingSampleCoverage(
                    total_samples=1,
                    samples_with_odds=0,
                    samples_with_asian_handicap=0,
                    samples_with_total_goals=0,
                )
            },
            by_season={2025: 1},
            by_weight={Decimal("0.80"): 1},
        ),
    )

    result = runner.invoke(app, ["samples", "report"])

    assert result.exit_code == 0
    assert "1" in result.stdout
    assert "La Liga" in result.stdout
