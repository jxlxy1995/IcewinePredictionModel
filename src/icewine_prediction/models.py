from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from icewine_prediction.database import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    country_or_region: Mapped[str] = mapped_column(String(80), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_name: Mapped[str | None] = mapped_column(String(80))
    source_league_id: Mapped[str | None] = mapped_column(String(120))
    aliases: Mapped[str | None] = mapped_column(Text)

    matches: Mapped[list["Match"]] = relationship(back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    english_name: Mapped[str | None] = mapped_column(String(120))
    country_or_region: Mapped[str | None] = mapped_column(String(80))
    source_name: Mapped[str | None] = mapped_column(String(80))
    source_team_id: Mapped[str | None] = mapped_column(String(120))
    aliases: Mapped[str | None] = mapped_column(Text)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    season: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    source_name: Mapped[str | None] = mapped_column(String(80))
    source_match_id: Mapped[str | None] = mapped_column(String(120))

    league: Mapped["League"] = relationship(back_populates="matches")
    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])
    odds_snapshots: Mapped[list["OddsSnapshot"]] = relationship(back_populates="match")


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(80), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(80), nullable=False)
    asian_handicap: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    home_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    away_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    total_line: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    over_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    under_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    match: Mapped["Match"] = relationship(back_populates="odds_snapshots")


class RecommendationRecord(Base):
    __tablename__ = "recommendation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    league_name: Mapped[str] = mapped_column(String(120), nullable=False)
    home_team_name: Mapped[str] = mapped_column(String(120), nullable=False)
    away_team_name: Mapped[str] = mapped_column(String(120), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    market_type: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[str] = mapped_column(String(20), nullable=False)
    market_line: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    model_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    market_implied_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    edge: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    confidence_grade: Mapped[str] = mapped_column(String(8), nullable=False)
    stake_units: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    home_expected_goals: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    away_expected_goals: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    settlement_result: Mapped[str | None] = mapped_column(String(20))
    profit_units: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))

    match: Mapped["Match"] = relationship()
