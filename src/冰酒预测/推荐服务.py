from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class 推荐结果:
    盘口类型: str
    方向: str
    信心等级: str
    建议手数: Decimal
    是否出手: bool
    价值差: Decimal
    风险标签: list[str]


等级顺序 = ["D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+", "S-", "S", "S+"]
等级手数 = {
    "D": Decimal("0"),
    "C-": Decimal("0.50"),
    "C": Decimal("0.50"),
    "C+": Decimal("0.75"),
    "B-": Decimal("1.00"),
    "B": Decimal("1.25"),
    "B+": Decimal("1.50"),
    "A-": Decimal("1.75"),
    "A": Decimal("2.00"),
    "A+": Decimal("2.25"),
    "S-": Decimal("2.50"),
    "S": Decimal("2.75"),
    "S+": Decimal("3.00"),
}


def _基础等级(价值差: Decimal, 同类回测收益率: Decimal) -> str:
    if 价值差 < Decimal("0.025") or 同类回测收益率 < Decimal("0.02"):
        return "D"
    if 价值差 < Decimal("0.045"):
        return "C+"
    if 价值差 < Decimal("0.080"):
        return "B"
    if 价值差 < Decimal("0.115"):
        return "A-"
    return "A+"


def _降低等级(等级: str, 次数: int) -> str:
    位置 = 等级顺序.index(等级)
    return 等级顺序[max(0, 位置 - 次数)]


def 根据信号生成推荐(
    盘口类型: str,
    方向: str,
    模型概率: Decimal,
    市场隐含概率: Decimal,
    同类回测收益率: Decimal,
    风险标签: list[str],
) -> 推荐结果:
    价值差 = 模型概率 - 市场隐含概率
    等级 = _基础等级(价值差, 同类回测收益率)
    if 风险标签 and 等级 != "D":
        等级 = _降低等级(等级, len(风险标签))
    手数 = 等级手数[等级]
    return 推荐结果(
        盘口类型=盘口类型,
        方向=方向,
        信心等级=等级,
        建议手数=手数,
        是否出手=手数 >= Decimal("0.50"),
        价值差=价值差,
        风险标签=风险标签,
    )
