from datetime import datetime

from sqlalchemy.orm import Session

from 冰酒预测.数据模型 import 比赛, 球队, 联赛


def 获取或创建联赛(会话: Session, 名称: str, 国家地区: str) -> 联赛:
    联赛记录 = 会话.query(联赛).filter_by(名称=名称).one_or_none()
    if 联赛记录 is not None:
        return 联赛记录
    联赛记录 = 联赛(名称=名称, 国家地区=国家地区, 级别=1, 是否启用=True, 优先级=0)
    会话.add(联赛记录)
    会话.flush()
    return 联赛记录


def 获取或创建球队(会话: Session, 标准中文名: str, 国家地区: str) -> 球队:
    球队记录 = 会话.query(球队).filter_by(标准中文名=标准中文名).one_or_none()
    if 球队记录 is not None:
        return 球队记录
    球队记录 = 球队(标准中文名=标准中文名, 国家地区=国家地区)
    会话.add(球队记录)
    会话.flush()
    return 球队记录


def 创建比赛(
    会话: Session,
    联赛名称: str,
    国家地区: str,
    主队名: str,
    客队名: str,
    开赛时间: datetime,
) -> 比赛:
    联赛记录 = 获取或创建联赛(会话, 联赛名称, 国家地区)
    主队 = 获取或创建球队(会话, 主队名, 国家地区)
    客队 = 获取或创建球队(会话, 客队名, 国家地区)
    比赛记录 = 比赛(联赛=联赛记录, 主队=主队, 客队=客队, 开赛时间=开赛时间, 状态="未开赛")
    会话.add(比赛记录)
    会话.commit()
    return 比赛记录
