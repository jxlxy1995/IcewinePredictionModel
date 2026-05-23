from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class 基础特征:
    主队进攻强度: Decimal
    客队进攻强度: Decimal
    主队防守强度: Decimal
    客队防守强度: Decimal


def 默认基础特征() -> 基础特征:
    return 基础特征(
        主队进攻强度=Decimal("1.00"),
        客队进攻强度=Decimal("1.00"),
        主队防守强度=Decimal("1.00"),
        客队防守强度=Decimal("1.00"),
    )
