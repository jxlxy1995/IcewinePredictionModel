from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from 冰酒预测.配置 import 默认数据库路径


class Base(DeclarativeBase):
    pass


def 创建数据库引擎(数据库路径: Path = 默认数据库路径) -> Engine:
    数据库路径.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{数据库路径}", future=True)


def 创建内存数据库() -> Engine:
    return create_engine("sqlite:///:memory:", future=True)


def 创建会话工厂(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def 初始化数据库(engine: Engine) -> None:
    from 冰酒预测 import 数据模型  # noqa: F401

    Base.metadata.create_all(engine)
