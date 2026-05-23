from dataclasses import dataclass
from decimal import Decimal
from math import exp, factorial


@dataclass(frozen=True)
class 基线预测结果:
    主队预期进球: Decimal
    客队预期进球: Decimal
    主队方向亚盘概率: Decimal
    大球概率: Decimal


def _泊松概率(lam: float, k: int) -> float:
    return exp(-lam) * lam**k / factorial(k)


def _赢盘概率(主队预期进球: float, 客队预期进球: float, 亚盘盘口: Decimal) -> Decimal:
    概率 = 0.0
    for 主队进球 in range(8):
        for 客队进球 in range(8):
            if 主队进球 - 客队进球 + float(亚盘盘口) > 0:
                概率 += _泊松概率(主队预期进球, 主队进球) * _泊松概率(客队预期进球, 客队进球)
    return Decimal(str(round(概率, 6)))


def _大球概率(主队预期进球: float, 客队预期进球: float, 大小球盘口: Decimal) -> Decimal:
    概率 = 0.0
    for 主队进球 in range(8):
        for 客队进球 in range(8):
            if 主队进球 + 客队进球 > float(大小球盘口):
                概率 += _泊松概率(主队预期进球, 主队进球) * _泊松概率(客队预期进球, 客队进球)
    return Decimal(str(round(概率, 6)))


def 基线预测(
    主队进攻强度: Decimal,
    客队进攻强度: Decimal,
    主队防守强度: Decimal,
    客队防守强度: Decimal,
    亚盘盘口: Decimal,
    大小球盘口: Decimal,
) -> 基线预测结果:
    主队预期 = Decimal("1.35") * 主队进攻强度 * 客队防守强度
    客队预期 = Decimal("1.05") * 客队进攻强度 * 主队防守强度
    return 基线预测结果(
        主队预期进球=主队预期,
        客队预期进球=客队预期,
        主队方向亚盘概率=_赢盘概率(float(主队预期), float(客队预期), 亚盘盘口),
        大球概率=_大球概率(float(主队预期), float(客队预期), 大小球盘口),
    )
