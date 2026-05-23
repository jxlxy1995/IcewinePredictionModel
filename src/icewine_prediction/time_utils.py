from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.config import BEIJING_TIMEZONE


def now_beijing() -> datetime:
    return datetime.now(ZoneInfo(BEIJING_TIMEZONE))
