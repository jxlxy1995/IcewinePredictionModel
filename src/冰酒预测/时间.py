from datetime import datetime
from zoneinfo import ZoneInfo

from 冰酒预测.配置 import 北京时间时区名


def 北京时间现在() -> datetime:
    return datetime.now(ZoneInfo(北京时间时区名))
