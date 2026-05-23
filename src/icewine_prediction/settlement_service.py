from decimal import Decimal


def _single_line_result(adjusted_margin: Decimal) -> str:
    if adjusted_margin > 0:
        return "win"
    if adjusted_margin == 0:
        return "push"
    return "loss"


def _split_quarter_line(line: Decimal) -> list[Decimal]:
    integer_part = int(line)
    decimal_part = abs(line - Decimal(integer_part))
    if decimal_part == Decimal("0.25"):
        offset = Decimal("0.50") if line > 0 else Decimal("-0.50")
        return [Decimal(integer_part), Decimal(integer_part) + offset]
    if decimal_part == Decimal("0.75"):
        half_offset = Decimal("0.50") if line > 0 else Decimal("-0.50")
        full_offset = Decimal("1.00") if line > 0 else Decimal("-1.00")
        return [Decimal(integer_part) + half_offset, Decimal(integer_part) + full_offset]
    return [line]


def _combine_results(results: list[str]) -> str:
    if len(results) == 1:
        return results[0]
    if results == ["win", "push"] or results == ["push", "win"]:
        return "half_win"
    if results == ["loss", "push"] or results == ["push", "loss"]:
        return "half_loss"
    if all(result == "win" for result in results):
        return "win"
    if all(result == "loss" for result in results):
        return "loss"
    return "push"


def settle_asian_handicap(home_score: int, away_score: int, line: Decimal, side: str) -> str:
    home_margin = Decimal(home_score - away_score)
    if side == "home":
        results = [_single_line_result(home_margin + split_line) for split_line in _split_quarter_line(line)]
    elif side == "away":
        results = [_single_line_result(-home_margin - split_line) for split_line in _split_quarter_line(line)]
    else:
        raise ValueError("side must be home or away")
    return _combine_results(results)


def settle_total_goals(home_score: int, away_score: int, line: Decimal, side: str) -> str:
    total_goals = Decimal(home_score + away_score)
    if side == "over":
        results = [_single_line_result(total_goals - split_line) for split_line in _split_quarter_line(line)]
    elif side == "under":
        results = [_single_line_result(split_line - total_goals) for split_line in _split_quarter_line(line)]
    else:
        raise ValueError("side must be over or under")
    return _combine_results(results)
