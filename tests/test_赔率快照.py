from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from 冰酒预测.比赛服务 import 创建比赛
from 冰酒预测.赔率服务 import 保存赔率快照, 查询比赛赔率快照


def test_同一场比赛可以保存多条赔率快照(会话):
    比赛记录 = 创建比赛(
        会话,
        联赛名称="英超",
        国家地区="英格兰",
        主队名="阿森纳",
        客队名="切尔西",
        开赛时间=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    保存赔率快照(
        会话,
        比赛记录.id,
        采集时间=datetime(2026, 5, 23, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        数据源="样例源",
        盘口源="样例公司",
        亚盘盘口=Decimal("-0.25"),
        主队水位=Decimal("0.92"),
        客队水位=Decimal("0.96"),
        大小球盘口=Decimal("2.50"),
        大球水位=Decimal("0.94"),
        小球水位=Decimal("0.94"),
    )
    保存赔率快照(
        会话,
        比赛记录.id,
        采集时间=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        数据源="样例源",
        盘口源="样例公司",
        亚盘盘口=Decimal("-0.50"),
        主队水位=Decimal("0.88"),
        客队水位=Decimal("1.00"),
        大小球盘口=Decimal("2.75"),
        大球水位=Decimal("0.90"),
        小球水位=Decimal("0.98"),
    )

    快照列表 = 查询比赛赔率快照(会话, 比赛记录.id)

    assert len(快照列表) == 2
    assert 快照列表[0].亚盘盘口 == Decimal("-0.25")
    assert 快照列表[1].亚盘盘口 == Decimal("-0.50")
