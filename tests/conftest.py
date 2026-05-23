import pytest

from 冰酒预测.数据库 import 创建内存数据库, 创建会话工厂, 初始化数据库


@pytest.fixture()
def 会话():
    engine = 创建内存数据库()
    初始化数据库(engine)
    会话工厂 = 创建会话工厂(engine)
    with 会话工厂() as session:
        yield session
