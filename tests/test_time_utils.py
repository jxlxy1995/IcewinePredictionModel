from datetime import timedelta

from icewine_prediction.time_utils import now_beijing


def test_now_beijing_returns_east_8_timezone():
    current = now_beijing()

    assert current.tzinfo is not None
    assert current.utcoffset() == timedelta(hours=8)
