from decimal import Decimal

from 冰酒预测.模型服务 import 基线预测


def test_基线预测返回亚盘和大小球概率():
    预测 = 基线预测(
        主队进攻强度=Decimal("1.30"),
        客队进攻强度=Decimal("1.00"),
        主队防守强度=Decimal("0.95"),
        客队防守强度=Decimal("1.10"),
        亚盘盘口=Decimal("-0.25"),
        大小球盘口=Decimal("2.50"),
    )

    assert Decimal("0") <= 预测.主队方向亚盘概率 <= Decimal("1")
    assert Decimal("0") <= 预测.大球概率 <= Decimal("1")
    assert 预测.主队预期进球 > Decimal("0")
    assert 预测.客队预期进球 > Decimal("0")
