from datetime import timedelta

from 冰酒预测.时间 import 北京时间现在


def test_北京时间现在_返回东八区时间():
    当前 = 北京时间现在()

    assert 当前.tzinfo is not None
    assert 当前.utcoffset() == timedelta(hours=8)
