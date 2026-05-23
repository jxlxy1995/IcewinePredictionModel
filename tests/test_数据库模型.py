from datetime import datetime
from zoneinfo import ZoneInfo

from 冰酒预测.数据模型 import 比赛, 球队, 联赛


def test_可以保存联赛球队和比赛(会话):
    联赛记录 = 联赛(名称="英超", 国家地区="英格兰", 级别=1, 是否启用=True, 优先级=10)
    主队 = 球队(标准中文名="阿森纳", 英文名="Arsenal", 国家地区="英格兰")
    客队 = 球队(标准中文名="切尔西", 英文名="Chelsea", 国家地区="英格兰")
    比赛记录 = 比赛(
        联赛=联赛记录,
        主队=主队,
        客队=客队,
        开赛时间=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        状态="未开赛",
    )

    会话.add(比赛记录)
    会话.commit()

    保存比赛 = 会话.query(比赛).one()
    assert 保存比赛.联赛.名称 == "英超"
    assert 保存比赛.主队.标准中文名 == "阿森纳"
    assert 保存比赛.客队.标准中文名 == "切尔西"
