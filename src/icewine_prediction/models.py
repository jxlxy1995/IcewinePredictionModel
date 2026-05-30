from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
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
    logo_url: Mapped[str | None] = mapped_column(String(255))
    flag_url: Mapped[str | None] = mapped_column(String(255))
    standings_supported: Mapped[bool | None] = mapped_column(Boolean)
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
    logo_url: Mapped[str | None] = mapped_column(String(255))
    aliases: Mapped[str | None] = mapped_column(Text)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    season: Mapped[int | None] = mapped_column(Integer)
    league_round: Mapped[str | None] = mapped_column(String(120))
    referee: Mapped[str | None] = mapped_column(String(120))
    fixture_timezone: Mapped[str | None] = mapped_column(String(80))
    fixture_timestamp: Mapped[int | None] = mapped_column(Integer)
    first_period_started_at: Mapped[int | None] = mapped_column(Integer)
    second_period_started_at: Mapped[int | None] = mapped_column(Integer)
    venue_id: Mapped[int | None] = mapped_column(Integer)
    venue_name: Mapped[str | None] = mapped_column(String(160))
    venue_city: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="scheduled")
    status_long: Mapped[str | None] = mapped_column(String(80))
    status_short: Mapped[str | None] = mapped_column(String(20))
    elapsed: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[int | None] = mapped_column(Integer)
    home_winner: Mapped[bool | None] = mapped_column(Boolean)
    away_winner: Mapped[bool | None] = mapped_column(Boolean)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    halftime_home_score: Mapped[int | None] = mapped_column(Integer)
    halftime_away_score: Mapped[int | None] = mapped_column(Integer)
    fulltime_home_score: Mapped[int | None] = mapped_column(Integer)
    fulltime_away_score: Mapped[int | None] = mapped_column(Integer)
    extratime_home_score: Mapped[int | None] = mapped_column(Integer)
    extratime_away_score: Mapped[int | None] = mapped_column(Integer)
    penalty_home_score: Mapped[int | None] = mapped_column(Integer)
    penalty_away_score: Mapped[int | None] = mapped_column(Integer)
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
    match_winner_home_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    match_winner_draw_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    match_winner_away_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    match: Mapped["Match"] = relationship(back_populates="odds_snapshots")


class OddsSourceMatch(Base):
    __tablename__ = "odds_source_matches"
    __table_args__ = (
        UniqueConstraint("match_id", "source_name", name="uq_odds_source_match"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_fixture_id: Mapped[str] = mapped_column(String(120), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    match_reason: Mapped[str] = mapped_column(Text, nullable=False)
    historical_odds_status: Mapped[str | None] = mapped_column(String(40))
    historical_odds_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    historical_odds_error: Mapped[str | None] = mapped_column(Text)

    match: Mapped["Match"] = relationship()


class HistoricalOddsSnapshot(Base):
    __tablename__ = "historical_odds_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "source_name",
            "bookmaker",
            "market_type",
            "market_id",
            "market_line",
            "outcome_side",
            "snapshot_time",
            name="uq_historical_odds_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_fixture_id: Mapped[str] = mapped_column(String(120), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(80), nullable=False)
    market_type: Mapped[str] = mapped_column(String(40), nullable=False)
    market_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market_name: Mapped[str] = mapped_column(String(120), nullable=False)
    market_line: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    outcome_side: Mapped[str] = mapped_column(String(20), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text)

    match: Mapped["Match"] = relationship()


class HistoricalOddsRawSnapshot(Base):
    __tablename__ = "historical_odds_raw_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "source_name",
            "bookmaker",
            "market_type",
            "market_id",
            "market_line",
            "outcome_side",
            "snapshot_time",
            name="uq_historical_odds_raw_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_fixture_id: Mapped[str] = mapped_column(String(120), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(80), nullable=False)
    market_type: Mapped[str] = mapped_column(String(40), nullable=False)
    market_id: Mapped[str] = mapped_column(String(80), nullable=False)
    market_name: Mapped[str] = mapped_column(String(120), nullable=False)
    market_line: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    outcome_side: Mapped[str] = mapped_column(String(20), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text)

    match: Mapped["Match"] = relationship()


class ExternalAlias(Base):
    __tablename__ = "external_aliases"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "source_name",
            "normalized_alias",
            name="uq_external_alias",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False)
    alias_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


class PaperRecommendationRecord(Base):
    __tablename__ = "paper_recommendation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    source_match_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    league_name: Mapped[str] = mapped_column(String(120), nullable=False)
    league_display_name: Mapped[str | None] = mapped_column(String(120))
    home_team_name: Mapped[str] = mapped_column(String(120), nullable=False)
    home_team_display_name: Mapped[str | None] = mapped_column(String(120))
    away_team_name: Mapped[str] = mapped_column(String(120), nullable=False)
    away_team_display_name: Mapped[str | None] = mapped_column(String(120))
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strategy_key: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    signal_version: Mapped[str | None] = mapped_column(String(40))
    market_type: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_handicap: Mapped[str | None] = mapped_column(String(40))
    original_recommended_handicap: Mapped[str | None] = mapped_column(String(40))
    line_bucket: Mapped[str | None] = mapped_column(String(40))
    risk_tags: Mapped[str | None] = mapped_column(Text)
    original_market_line: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    original_odds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    current_market_line: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    current_odds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    model_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    market_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    edge: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    stake_units: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    is_manually_adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual_note: Mapped[str | None] = mapped_column(Text)
    settlement_result: Mapped[str | None] = mapped_column(String(20))
    profit_units: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    match: Mapped["Match"] = relationship()


class DataSyncRun(Base):
    __tablename__ = "data_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_type: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_tag: Mapped[str] = mapped_column(String(40), nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(80))
    error_step: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    dataset_path: Mapped[str | None] = mapped_column(String(255))
    dataset_report_path: Mapped[str | None] = mapped_column(String(255))
    qa_report_path: Mapped[str | None] = mapped_column(String(255))
    market_baseline_report_path: Mapped[str | None] = mapped_column(String(255))
    feature_path: Mapped[str | None] = mapped_column(String(255))
    feature_report_path: Mapped[str | None] = mapped_column(String(255))
    dynamic_feature_path: Mapped[str | None] = mapped_column(String(255))
    dynamic_feature_report_path: Mapped[str | None] = mapped_column(String(255))
    away_cover_stability_report_path: Mapped[str | None] = mapped_column(String(255))
    dataset_rows: Mapped[int | None] = mapped_column(Integer)
    eligible_matches: Mapped[int | None] = mapped_column(Integer)
    complete_matches: Mapped[int | None] = mapped_column(Integer)
    coverage_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    last_trained_match_id: Mapped[int | None] = mapped_column(Integer)
    last_trained_match_summary: Mapped[str | None] = mapped_column(String(255))
    last_trained_kickoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_complete_matches: Mapped[int | None] = mapped_column(Integer)
