from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from 冰酒预测.数据库 import Base


class 联赛(Base):
    __tablename__ = "联赛"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    名称: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    国家地区: Mapped[str] = mapped_column(String(80), nullable=False)
    级别: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    是否启用: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    优先级: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    数据源联赛ID: Mapped[str | None] = mapped_column(String(120))
    别名: Mapped[str | None] = mapped_column(Text)

    比赛列表: Mapped[list["比赛"]] = relationship(back_populates="联赛")


class 球队(Base):
    __tablename__ = "球队"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    标准中文名: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    英文名: Mapped[str | None] = mapped_column(String(120))
    国家地区: Mapped[str | None] = mapped_column(String(80))
    数据源球队ID: Mapped[str | None] = mapped_column(String(120))
    别名: Mapped[str | None] = mapped_column(Text)


class 比赛(Base):
    __tablename__ = "比赛"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    联赛id: Mapped[int] = mapped_column(ForeignKey("联赛.id"), nullable=False)
    主队id: Mapped[int] = mapped_column(ForeignKey("球队.id"), nullable=False)
    客队id: Mapped[int] = mapped_column(ForeignKey("球队.id"), nullable=False)
    开赛时间: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    状态: Mapped[str] = mapped_column(String(40), nullable=False, default="未开赛")
    主队比分: Mapped[int | None] = mapped_column(Integer)
    客队比分: Mapped[int | None] = mapped_column(Integer)
    数据源比赛ID: Mapped[str | None] = mapped_column(String(120))

    联赛: Mapped["联赛"] = relationship(back_populates="比赛列表")
    主队: Mapped["球队"] = relationship(foreign_keys=[主队id])
    客队: Mapped["球队"] = relationship(foreign_keys=[客队id])
    赔率快照列表: Mapped[list["赔率快照"]] = relationship(back_populates="比赛")


class 赔率快照(Base):
    __tablename__ = "赔率快照"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    比赛id: Mapped[int] = mapped_column(ForeignKey("比赛.id"), nullable=False)
    采集时间: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    数据源: Mapped[str] = mapped_column(String(80), nullable=False)
    盘口源: Mapped[str] = mapped_column(String(80), nullable=False)
    亚盘盘口: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    主队水位: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    客队水位: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    大小球盘口: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    大球水位: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    小球水位: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    比赛: Mapped["比赛"] = relationship(back_populates="赔率快照列表")
