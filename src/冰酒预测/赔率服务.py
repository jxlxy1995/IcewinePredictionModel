from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from 冰酒预测.数据模型 import 赔率快照


def 保存赔率快照(
    会话: Session,
    比赛id: int,
    采集时间: datetime,
    数据源: str,
    盘口源: str,
    亚盘盘口: Decimal | None,
    主队水位: Decimal | None,
    客队水位: Decimal | None,
    大小球盘口: Decimal | None,
    大球水位: Decimal | None,
    小球水位: Decimal | None,
) -> 赔率快照:
    快照 = 赔率快照(
        比赛id=比赛id,
        采集时间=采集时间,
        数据源=数据源,
        盘口源=盘口源,
        亚盘盘口=亚盘盘口,
        主队水位=主队水位,
        客队水位=客队水位,
        大小球盘口=大小球盘口,
        大球水位=大球水位,
        小球水位=小球水位,
    )
    会话.add(快照)
    会话.commit()
    return 快照


def 查询比赛赔率快照(会话: Session, 比赛id: int) -> list[赔率快照]:
    return (
        会话.query(赔率快照)
        .filter_by(比赛id=比赛id)
        .order_by(赔率快照.采集时间.asc())
        .all()
    )
