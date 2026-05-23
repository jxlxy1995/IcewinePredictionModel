from decimal import Decimal


def _单盘口结果(净胜调整值: Decimal) -> str:
    if 净胜调整值 > 0:
        return "赢"
    if 净胜调整值 == 0:
        return "走水"
    return "输"


def _拆分盘口(盘口: Decimal) -> list[Decimal]:
    整数部分 = int(盘口)
    小数部分 = abs(盘口 - Decimal(整数部分))
    if 小数部分 == Decimal("0.25"):
        偏移 = Decimal("0.50") if 盘口 > 0 else Decimal("-0.50")
        return [Decimal(整数部分), Decimal(整数部分) + 偏移]
    if 小数部分 == Decimal("0.75"):
        半球偏移 = Decimal("0.50") if 盘口 > 0 else Decimal("-0.50")
        一球偏移 = Decimal("1.00") if 盘口 > 0 else Decimal("-1.00")
        return [Decimal(整数部分) + 半球偏移, Decimal(整数部分) + 一球偏移]
    return [盘口]


def _合并结果(结果列表: list[str]) -> str:
    if len(结果列表) == 1:
        return 结果列表[0]
    if 结果列表 == ["赢", "走水"] or 结果列表 == ["走水", "赢"]:
        return "赢半"
    if 结果列表 == ["输", "走水"] or 结果列表 == ["走水", "输"]:
        return "输半"
    if all(结果 == "赢" for 结果 in 结果列表):
        return "赢"
    if all(结果 == "输" for 结果 in 结果列表):
        return "输"
    return "走水"


def 结算亚盘(主队比分: int, 客队比分: int, 盘口: Decimal, 方向: str) -> str:
    主队净胜 = Decimal(主队比分 - 客队比分)
    if 方向 == "主队":
        结果列表 = [_单盘口结果(主队净胜 + 子盘口) for 子盘口 in _拆分盘口(盘口)]
    elif 方向 == "客队":
        结果列表 = [_单盘口结果(-主队净胜 - 子盘口) for 子盘口 in _拆分盘口(盘口)]
    else:
        raise ValueError("方向必须是主队或客队")
    return _合并结果(结果列表)


def 结算大小球(主队比分: int, 客队比分: int, 盘口: Decimal, 方向: str) -> str:
    总进球 = Decimal(主队比分 + 客队比分)
    if 方向 == "大球":
        结果列表 = [_单盘口结果(总进球 - 子盘口) for 子盘口 in _拆分盘口(盘口)]
    elif 方向 == "小球":
        结果列表 = [_单盘口结果(子盘口 - 总进球) for 子盘口 in _拆分盘口(盘口)]
    else:
        raise ValueError("方向必须是大球或小球")
    return _合并结果(结果列表)
