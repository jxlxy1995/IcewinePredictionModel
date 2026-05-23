from decimal import Decimal

from 冰酒预测.推荐服务 import 根据信号生成推荐


def test_低价值差不出手():
    推荐 = 根据信号生成推荐(
        盘口类型="亚盘",
        方向="主队",
        模型概率=Decimal("0.515"),
        市场隐含概率=Decimal("0.505"),
        同类回测收益率=Decimal("0.01"),
        风险标签=[],
    )

    assert 推荐.信心等级 == "D"
    assert 推荐.建议手数 == Decimal("0")
    assert 推荐.是否出手 is False


def test_中等价值差生成B级推荐():
    推荐 = 根据信号生成推荐(
        盘口类型="大小球",
        方向="大球",
        模型概率=Decimal("0.570"),
        市场隐含概率=Decimal("0.505"),
        同类回测收益率=Decimal("0.06"),
        风险标签=[],
    )

    assert 推荐.信心等级 == "B"
    assert 推荐.建议手数 == Decimal("1.25")
    assert 推荐.是否出手 is True


def test_高风险会降低推荐等级():
    推荐 = 根据信号生成推荐(
        盘口类型="亚盘",
        方向="客队",
        模型概率=Decimal("0.610"),
        市场隐含概率=Decimal("0.505"),
        同类回测收益率=Decimal("0.08"),
        风险标签=["临场盘口剧烈变化"],
    )

    assert 推荐.信心等级 == "B+"
    assert 推荐.建议手数 == Decimal("1.50")
