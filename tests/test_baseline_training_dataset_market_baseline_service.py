from decimal import Decimal

from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    build_baseline_training_dataset_market_baseline_report,
    format_baseline_training_dataset_market_baseline_report,
)


def test_build_market_baseline_report_scores_three_markets_from_csv(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                ",".join(_fieldnames()),
                ",".join(
                    _row(
                        match_result="home_win",
                        asian_probs=("0.6000", "0.4000"),
                        asian_odds=("1.667", "2.500"),
                        asian_results=("win", "loss"),
                        total_probs=("0.5500", "0.4500"),
                        total_odds=("1.818", "2.222"),
                        total_results=("half_win", "half_loss"),
                        winner_probs=("0.5000", "0.3000", "0.2000"),
                        winner_odds=("2.000", "3.333", "5.000"),
                        winner_results=("win", "loss", "loss"),
                    )
                ),
                ",".join(
                    _row(
                        match_result="away_win",
                        asian_probs=("0.4000", "0.6000"),
                        asian_odds=("2.500", "1.667"),
                        asian_results=("loss", "win"),
                        total_probs=("0.5500", "0.4500"),
                        total_odds=("1.818", "2.222"),
                        total_results=("loss", "win"),
                        winner_probs=("0.5000", "0.3000", "0.2000"),
                        winner_odds=("2.000", "3.333", "5.000"),
                        winner_results=("loss", "loss", "win"),
                    )
                ),
                ",".join(
                    _row(
                        match_result="draw",
                        asian_probs=("0.5000", "0.5000"),
                        asian_odds=("1.950", "1.950"),
                        asian_results=("push", "push"),
                        total_probs=("0.5000", "0.5000"),
                        total_odds=("1.950", "1.950"),
                        total_results=("push", "push"),
                        winner_probs=("0.3000", "0.4000", "0.3000"),
                        winner_odds=("3.333", "2.500", "3.333"),
                        winner_results=("loss", "win", "loss"),
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_baseline_training_dataset_market_baseline_report(csv_path)

    assert report.row_count == 3
    assert report.total_evaluated_market_samples == 7
    assert report.market_reports["match_winner"].evaluated_count == 3
    assert report.market_reports["match_winner"].accuracy == Decimal("0.6667")
    assert report.market_reports["match_winner"].flat_bet_count == 3
    assert report.market_reports["match_winner"].flat_bet_profit_units == Decimal("1.5000")
    assert report.market_reports["match_winner"].flat_bet_roi == Decimal("0.5000")
    assert report.market_reports["asian_handicap"].evaluated_count == 2
    assert report.market_reports["asian_handicap"].skipped_count == 1
    assert report.market_reports["total_goals"].evaluated_count == 2
    assert report.market_reports["total_goals"].skipped_count == 1


def test_format_market_baseline_report_outputs_markdown_sections(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        ",".join(_fieldnames())
        + "\n"
        + ",".join(
            _row(
                match_result="home_win",
                asian_probs=("0.6000", "0.4000"),
                asian_odds=("1.667", "2.500"),
                asian_results=("win", "loss"),
                total_probs=("0.5500", "0.4500"),
                total_odds=("1.818", "2.222"),
                total_results=("win", "loss"),
                winner_probs=("0.5000", "0.3000", "0.2000"),
                winner_odds=("2.000", "3.333", "5.000"),
                winner_results=("win", "loss", "loss"),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    text = format_baseline_training_dataset_market_baseline_report(
        build_baseline_training_dataset_market_baseline_report(csv_path)
    )

    assert "# Close-Market Baseline Evaluation" in text
    assert "Rows | 1" in text
    assert "match_winner" in text
    assert "Flat bet ROI" in text


def _fieldnames() -> list[str]:
    return [
        "match_result",
        "asian_handicap_home_odds",
        "asian_handicap_away_odds",
        "asian_handicap_home_implied_probability",
        "asian_handicap_away_implied_probability",
        "asian_handicap_overround",
        "asian_handicap_home_result",
        "asian_handicap_away_result",
        "total_goals_over_odds",
        "total_goals_under_odds",
        "total_goals_over_implied_probability",
        "total_goals_under_implied_probability",
        "total_goals_overround",
        "total_goals_over_result",
        "total_goals_under_result",
        "match_winner_home_odds",
        "match_winner_draw_odds",
        "match_winner_away_odds",
        "match_winner_home_implied_probability",
        "match_winner_draw_implied_probability",
        "match_winner_away_implied_probability",
        "match_winner_overround",
        "match_winner_home_result",
        "match_winner_draw_result",
        "match_winner_away_result",
    ]


def _row(
    *,
    match_result: str,
    asian_probs: tuple[str, str],
    asian_odds: tuple[str, str],
    asian_results: tuple[str, str],
    total_probs: tuple[str, str],
    total_odds: tuple[str, str],
    total_results: tuple[str, str],
    winner_probs: tuple[str, str, str],
    winner_odds: tuple[str, str, str],
    winner_results: tuple[str, str, str],
) -> list[str]:
    return [
        match_result,
        asian_odds[0],
        asian_odds[1],
        asian_probs[0],
        asian_probs[1],
        str(sum(Decimal(value) for value in asian_probs)),
        asian_results[0],
        asian_results[1],
        total_odds[0],
        total_odds[1],
        total_probs[0],
        total_probs[1],
        str(sum(Decimal(value) for value in total_probs)),
        total_results[0],
        total_results[1],
        winner_odds[0],
        winner_odds[1],
        winner_odds[2],
        winner_probs[0],
        winner_probs[1],
        winner_probs[2],
        str(sum(Decimal(value) for value in winner_probs)),
        winner_results[0],
        winner_results[1],
        winner_results[2],
    ]
