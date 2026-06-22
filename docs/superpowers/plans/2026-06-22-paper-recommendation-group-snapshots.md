# Paper Recommendation Group Snapshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist paper recommendation confidence groups as versioned snapshots, generate them for future manual and automated paper records, support marked historical backfill, and report snapshot-based replay metrics.

**Architecture:** Add a focused snapshot model plus a service that reuses `build_paper_confidence_workspace(...)` without redefining confidence rules. Hook that service into paper record creation and automation execution, then add CLI commands for historical backfill and snapshot-based reports. Keep Web UI changes minimal and do not migrate old `recommendation_records`.

**Tech Stack:** Python 3.12, SQLAlchemy, SQLite schema evolution, Typer CLI, pytest, existing paper recommendation and Bark services.

---

## Source Design

Read first:

- `docs/superpowers/specs/2026-06-22-paper-recommendation-group-snapshots-design.md`
- `Agent.md`
- `memory.md`

Hard constraints:

- Do not migrate old `recommendation_records`.
- Keep the current paper chain as the main real-use tracking chain.
- Recommendation group identity must match current confidence workspace semantics: `match_id + market_type + side`.
- Historical backfill snapshots must be clearly marked and must not pretend to be original Web/Bark scores.
- Replay/report weighted profit must use the frozen snapshot stake, not a dynamically recalculated current stake.
- Report line buckets together with `market_type`; do not interpret total-goals 2.5 and Asian-handicap 2.5 as the same bucket.

## File Structure

Backend files:

- Modify `src/icewine_prediction/models.py`
  - Add `PaperRecommendationGroupSnapshot`.
- Modify `src/icewine_prediction/database.py`
  - Ensure existing SQLite DBs create `paper_recommendation_group_snapshots`.
- Create `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`
  - Snapshot creation, idempotency, backfill, report aggregation, Markdown formatting.
- Modify `src/icewine_prediction/paper_recommendation_tracking_service.py`
  - Optionally expose a helper for affected record ids only if needed; avoid moving existing tracking logic.
- Modify `src/icewine_prediction/paper_automation_service.py`
  - Generate snapshots for created records, use generated groups for Bark, include snapshot ids in task payload.
- Modify `src/icewine_prediction/web_api.py`
  - Generate snapshots after single and batch paper record creation.
- Modify `src/icewine_prediction/cli.py`
  - Add `records snapshots-backfill` and `records snapshot-report`.
- Modify `memory.md`
  - Add stable decision that paper group snapshots are the frozen execution-advice layer.

Tests:

- Create `tests/test_paper_recommendation_group_snapshot_service.py`
  - Core snapshot generation, idempotency, versions, backfill, report buckets.
- Modify `tests/test_database_schema.py`
  - Existing SQLite table creation for snapshots.
- Modify `tests/test_paper_automation_service.py`
  - Automation payload includes snapshot ids and Bark groups come from snapshot generation path.
- Modify `tests/test_web_console_api.py`
  - Manual single/batch record creation generates snapshots.
- Add or modify CLI tests if the project already has CLI runner coverage for `records`; otherwise cover CLI through service tests and smoke command in final verification.

## Task 1: Add Snapshot Model And SQLite Schema

**Files:**
- Modify: `src/icewine_prediction/models.py`
- Modify: `src/icewine_prediction/database.py`
- Modify: `tests/test_database_schema.py`
- Create: `tests/test_paper_recommendation_group_snapshot_service.py`

- [ ] **Step 1: Add failing schema tests**

Append to `tests/test_database_schema.py`:

```python
def test_initialize_database_creates_paper_group_snapshots_for_existing_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        create table paper_recommendation_records (
            id integer primary key,
            match_id integer not null,
            source_match_id varchar(120),
            created_at datetime not null,
            updated_at datetime not null,
            league_name varchar(120) not null,
            home_team_name varchar(120) not null,
            away_team_name varchar(120) not null,
            kickoff_time datetime not null,
            strategy_key varchar(80) not null,
            strategy_display_name varchar(120) not null,
            model_name varchar(120) not null,
            market_type varchar(40) not null,
            side varchar(20) not null,
            original_market_line numeric(5, 2) not null,
            original_odds numeric(6, 3) not null,
            current_market_line numeric(5, 2) not null,
            current_odds numeric(6, 3) not null,
            edge numeric(8, 4) not null,
            stake_units numeric(6, 2) not null,
            status varchar(20) not null
        )
        """
    )
    connection.close()

    engine = create_database_engine(database_path)
    initialize_database(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    snapshot_columns = {
        column["name"]
        for column in inspector.get_columns("paper_recommendation_group_snapshots")
    }
    assert "paper_recommendation_group_snapshots" in table_names
    assert {
        "snapshot_source",
        "snapshot_version",
        "group_key",
        "signal_record_ids_json",
        "confidence_score",
        "suggested_stake_units",
        "line_bucket",
        "is_backfilled",
    }.issubset(snapshot_columns)
```

Create `tests/test_paper_recommendation_group_snapshot_service.py` with an initial model test:

```python
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    League,
    Match,
    PaperRecommendationGroupSnapshot,
    PaperRecommendationRecord,
    Team,
)


BEIJING = ZoneInfo("Asia/Shanghai")


def test_snapshot_model_can_be_inserted(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    snapshot = PaperRecommendationGroupSnapshot(
        created_at=_now(),
        snapshot_source="manual_record",
        snapshot_version="paper_confidence_v1",
        group_key=f"{match.id}:asian_handicap:away_cover",
        match_id=match.id,
        market_type="asian_handicap",
        side="away_cover",
        representative_record_id=record.id,
        signal_record_ids_json=json.dumps([record.id]),
        triggered_strategy_keys_json=json.dumps([record.strategy_key]),
        triggered_strategy_display_names_json=json.dumps([record.strategy_display_name]),
        signal_families_json=json.dumps(["asian_away_hgb"]),
        confidence_score=60,
        suggested_stake_units=Decimal("0.75"),
        stake_cap_reason="single_family_limited_history",
        recommendation_text="客队 +0.50",
        representative_market_line=Decimal("-0.50"),
        representative_odds=Decimal("1.930"),
        line_bucket="away_underdog",
        status="pending",
        settlement_result=None,
        flat_profit_units=Decimal("0.000"),
        weighted_profit_units=Decimal("0.000"),
        is_backfilled=False,
        source_record_created_at_min=record.created_at,
        source_record_created_at_max=record.created_at,
    )

    session.add(snapshot)
    session.commit()

    loaded = session.get(PaperRecommendationGroupSnapshot, snapshot.id)
    assert loaded is not None
    assert loaded.group_key == f"{match.id}:asian_handicap:away_cover"
    assert loaded.suggested_stake_units == Decimal("0.75")
    assert loaded.line_bucket == "away_underdog"


def _now() -> datetime:
    return datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING)


def _seed_match(session, *, home_score=None, away_score=None, status="scheduled") -> Match:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country="Japan",
        is_enabled=True,
    )
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Yokohama F. Marinos")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Vissel Kobe")
    match = Match(
        source_name="api-football",
        source_match_id="fixture-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 22, 19, 0, tzinfo=BEIJING),
        status=status,
        home_score=home_score,
        away_score=away_score,
        season=2026,
    )
    session.add_all([league, home, away, match])
    session.commit()
    return match


def _paper_record(session, match: Match, **overrides) -> PaperRecommendationRecord:
    values = {
        "match_id": match.id,
        "source_match_id": match.source_match_id,
        "created_at": _now(),
        "updated_at": _now(),
        "league_name": match.league.name,
        "league_display_name": "日职联",
        "home_team_name": match.home_team.canonical_name,
        "home_team_display_name": "横滨水手",
        "away_team_name": match.away_team.canonical_name,
        "away_team_display_name": "神户胜利船",
        "kickoff_time": match.kickoff_time,
        "strategy_key": "asian_away_cover_hgb_edge_v1",
        "strategy_display_name": "亚盘客队方向 HGB edge v1",
        "model_name": "hgb",
        "signal_version": "v1",
        "market_type": "asian_handicap",
        "side": "away_cover",
        "recommended_handicap": "客队 +0.50",
        "original_recommended_handicap": "客队 +0.50",
        "line_bucket": "away_underdog",
        "risk_tags": "line_bucket:away_underdog",
        "original_market_line": Decimal("-0.50"),
        "original_odds": Decimal("1.930"),
        "current_market_line": Decimal("-0.50"),
        "current_odds": Decimal("1.930"),
        "model_probability": Decimal("0.5600"),
        "market_probability": Decimal("0.5100"),
        "edge": Decimal("0.1000"),
        "scoring_edge": Decimal("0.1000"),
        "stake_units": Decimal("1.00"),
        "status": "pending",
        "is_manually_adjusted": False,
    }
    values.update(overrides)
    record = PaperRecommendationRecord(**values)
    session.add(record)
    session.commit()
    return record
```

- [ ] **Step 2: Run failing schema tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_database_schema.py::test_initialize_database_creates_paper_group_snapshots_for_existing_sqlite_database tests/test_paper_recommendation_group_snapshot_service.py::test_snapshot_model_can_be_inserted -q
```

Expected: FAIL because `PaperRecommendationGroupSnapshot` and table are not defined.

- [ ] **Step 3: Add SQLAlchemy model**

In `src/icewine_prediction/models.py`, add after `PaperRecommendationRecord`:

```python
class PaperRecommendationGroupSnapshot(Base):
    __tablename__ = "paper_recommendation_group_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_source: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_version: Mapped[str] = mapped_column(String(40), nullable=False)
    group_key: Mapped[str] = mapped_column(String(160), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    market_type: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[str] = mapped_column(String(20), nullable=False)
    representative_record_id: Mapped[int] = mapped_column(
        ForeignKey("paper_recommendation_records.id"),
        nullable=False,
    )
    signal_record_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_strategy_keys_json: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_strategy_display_names_json: Mapped[str] = mapped_column(Text, nullable=False)
    signal_families_json: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_stake_units: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    stake_cap_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    recommendation_text: Mapped[str | None] = mapped_column(String(80))
    representative_market_line: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    representative_odds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    line_bucket: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    settlement_result: Mapped[str | None] = mapped_column(String(20))
    flat_profit_units: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    weighted_profit_units: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    is_backfilled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_record_created_at_min: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_record_created_at_max: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    match: Mapped["Match"] = relationship()
    representative_record: Mapped["PaperRecommendationRecord"] = relationship()
```

- [ ] **Step 4: Add SQLite schema guard**

In `src/icewine_prediction/database.py`, inside `with engine.begin() as connection:` and near the existing `paper_automation_tasks` table guard, add:

```python
        if "paper_recommendation_group_snapshots" not in table_names:
            Base.metadata.tables["paper_recommendation_group_snapshots"].create(
                connection,
                checkfirst=True,
            )
```

- [ ] **Step 5: Run schema tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_database_schema.py::test_initialize_database_creates_paper_group_snapshots_for_existing_sqlite_database tests/test_paper_recommendation_group_snapshot_service.py::test_snapshot_model_can_be_inserted -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/icewine_prediction/models.py src/icewine_prediction/database.py tests/test_database_schema.py tests/test_paper_recommendation_group_snapshot_service.py
git commit -m "Add paper recommendation group snapshot model"
```

## Task 2: Add Snapshot Creation Service

**Files:**
- Create: `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`
- Modify: `tests/test_paper_recommendation_group_snapshot_service.py`

- [ ] **Step 1: Add failing service tests**

Append to `tests/test_paper_recommendation_group_snapshot_service.py`:

```python
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    create_group_snapshots_for_record_ids,
)


def test_create_group_snapshots_groups_same_match_market_and_side(session):
    match = _seed_match(session)
    first = _paper_record(session, match, edge=Decimal("0.1200"), scoring_edge=Decimal("0.1200"))
    second = _paper_record(
        session,
        match,
        strategy_key="asian_away_cover_hgb_bucket_v2",
        strategy_display_name="亚盘客队方向 HGB bucket v2",
        signal_version="v2",
        risk_tags="line_bucket:away_underdog,strategy:bucket_v2",
        edge=Decimal("0.2200"),
        scoring_edge=Decimal("0.2200"),
    )

    results = create_group_snapshots_for_record_ids(
        session,
        [first.id, second.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )

    assert len(results) == 1
    snapshot = results[0].snapshot
    assert snapshot.snapshot_version == PAPER_CONFIDENCE_SNAPSHOT_VERSION
    assert snapshot.snapshot_source == "manual_record"
    assert snapshot.group_key == f"{match.id}:asian_handicap:away_cover"
    assert json.loads(snapshot.signal_record_ids_json) == [first.id, second.id]
    assert json.loads(snapshot.triggered_strategy_keys_json) == [
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    ]
    assert snapshot.confidence_score >= 70
    assert snapshot.suggested_stake_units >= Decimal("1.00")
    assert snapshot.line_bucket == "away_underdog"


def test_create_group_snapshots_keeps_different_markets_separate(session):
    match = _seed_match(session)
    asian = _paper_record(session, match)
    total = _paper_record(
        session,
        match,
        strategy_key="total_goals_hgb_bucket_v2",
        strategy_display_name="大小球 HGB bucket v2",
        model_name="hgb_total_goals",
        market_type="total_goals",
        side="under",
        recommended_handicap="小 2.50",
        original_recommended_handicap="小 2.50",
        line_bucket="mid_2.50",
        risk_tags="line_bucket:mid_2.50,strategy:total_goals_bucket_v2",
        original_market_line=Decimal("2.50"),
        current_market_line=Decimal("2.50"),
        edge=Decimal("0.1300"),
        scoring_edge=Decimal("0.1300"),
    )

    results = create_group_snapshots_for_record_ids(
        session,
        [asian.id, total.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )

    assert sorted(result.snapshot.market_type for result in results) == [
        "asian_handicap",
        "total_goals",
    ]
    assert sorted(result.snapshot.line_bucket for result in results) == [
        "away_underdog",
        "mid_2.50",
    ]


def test_create_group_snapshots_is_idempotent_per_source_version_group_and_signal_set(session):
    match = _seed_match(session)
    record = _paper_record(session, match)

    first = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    second = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    third = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        snapshot_version="paper_confidence_v2",
        created_at=_now(),
    )

    assert len(first) == 1
    assert second == []
    assert len(third) == 1
```

- [ ] **Step 2: Run failing service tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py -q
```

Expected: FAIL because `paper_recommendation_group_snapshot_service.py` does not exist.

- [ ] **Step 3: Create snapshot service**

Create `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from icewine_prediction.models import (
    PaperRecommendationGroupSnapshot,
    PaperRecommendationRecord,
)
from icewine_prediction.paper_confidence_service import (
    PaperConfidenceGroup,
    build_paper_confidence_workspace,
)


PAPER_CONFIDENCE_SNAPSHOT_VERSION = "paper_confidence_v1"
MONEY_QUANT = Decimal("0.001")


@dataclass(frozen=True)
class CreatedPaperGroupSnapshot:
    snapshot: PaperRecommendationGroupSnapshot
    group: PaperConfidenceGroup


def create_group_snapshots_for_record_ids(
    session: Session,
    record_ids: list[int],
    *,
    snapshot_source: str,
    created_at: datetime,
    snapshot_version: str = PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    is_backfilled: bool = False,
) -> list[CreatedPaperGroupSnapshot]:
    if not record_ids:
        return []
    record_id_set = set(record_ids)
    all_records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    workspace = build_paper_confidence_workspace(all_records)
    created: list[CreatedPaperGroupSnapshot] = []
    for group in workspace.groups:
        if not record_id_set.intersection(group.signal_record_ids):
            continue
        signal_record_ids = tuple(sorted(group.signal_record_ids))
        signal_record_ids_json = _json_list(signal_record_ids)
        duplicate = (
            session.query(PaperRecommendationGroupSnapshot)
            .filter(PaperRecommendationGroupSnapshot.snapshot_source == snapshot_source)
            .filter(PaperRecommendationGroupSnapshot.snapshot_version == snapshot_version)
            .filter(PaperRecommendationGroupSnapshot.group_key == group.group_key)
            .filter(PaperRecommendationGroupSnapshot.signal_record_ids_json == signal_record_ids_json)
            .first()
        )
        if duplicate is not None:
            continue
        group_records = [
            record
            for record in all_records
            if record.id in set(signal_record_ids)
        ]
        source_times = [record.created_at for record in group_records]
        snapshot = PaperRecommendationGroupSnapshot(
            created_at=created_at,
            snapshot_source=snapshot_source,
            snapshot_version=snapshot_version,
            group_key=group.group_key,
            match_id=group.match_id,
            market_type=group.market_type,
            side=group.logical_side,
            representative_record_id=group.representative_record_id,
            signal_record_ids_json=signal_record_ids_json,
            triggered_strategy_keys_json=_json_list(group.triggered_strategy_keys),
            triggered_strategy_display_names_json=_json_list(group.triggered_strategy_display_names),
            signal_families_json=_json_list(group.signal_families),
            confidence_score=group.confidence_score,
            suggested_stake_units=group.suggested_stake_units,
            stake_cap_reason=group.stake_cap_reason,
            recommendation_text=group.recommendation_text,
            representative_market_line=group.representative_market_line,
            representative_odds=group.representative_odds,
            line_bucket=_line_bucket_for_group(group_records, group.representative_record_id),
            status=group.status,
            settlement_result=group.settlement_result,
            flat_profit_units=group.flat_profit_units.quantize(MONEY_QUANT),
            weighted_profit_units=group.weighted_profit_units.quantize(MONEY_QUANT),
            is_backfilled=is_backfilled,
            source_record_created_at_min=min(source_times),
            source_record_created_at_max=max(source_times),
        )
        session.add(snapshot)
        session.flush()
        created.append(CreatedPaperGroupSnapshot(snapshot=snapshot, group=group))
    session.commit()
    return created


def _json_list(values) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def _line_bucket_for_group(
    records: list[PaperRecommendationRecord],
    representative_record_id: int,
) -> str | None:
    for record in records:
        if record.id == representative_record_id:
            return record.line_bucket
    return records[0].line_bucket if records else None
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/icewine_prediction/paper_recommendation_group_snapshot_service.py tests/test_paper_recommendation_group_snapshot_service.py
git commit -m "Add paper group snapshot creation service"
```

## Task 3: Add Snapshot Backfill And Report Service

**Files:**
- Modify: `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`
- Modify: `tests/test_paper_recommendation_group_snapshot_service.py`

- [ ] **Step 1: Add failing backfill and report tests**

Append:

```python
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    build_snapshot_report,
    format_snapshot_report,
    backfill_group_snapshots,
)
from icewine_prediction.paper_recommendation_tracking_service import settle_paper_records


def test_backfill_group_snapshots_marks_historical_backfill(session):
    match = _seed_match(session)
    record = _paper_record(session, match)

    result = backfill_group_snapshots(
        session,
        from_date=datetime(2026, 6, 1, tzinfo=BEIJING),
        to_date=datetime(2026, 6, 30, 23, 59, tzinfo=BEIJING),
        created_at=_now(),
    )

    assert result.created_count == 1
    snapshot = session.query(PaperRecommendationGroupSnapshot).one()
    assert snapshot.is_backfilled is True
    assert snapshot.snapshot_source == "historical_backfill"
    assert snapshot.source_record_created_at_min == record.created_at


def test_backfill_group_snapshots_dry_run_does_not_write(session):
    match = _seed_match(session)
    _paper_record(session, match)

    result = backfill_group_snapshots(
        session,
        from_date=datetime(2026, 6, 1, tzinfo=BEIJING),
        to_date=datetime(2026, 6, 30, 23, 59, tzinfo=BEIJING),
        created_at=_now(),
        dry_run=True,
    )

    assert result.created_count == 1
    assert session.query(PaperRecommendationGroupSnapshot).count() == 0


def test_snapshot_report_uses_frozen_stake_and_market_aware_line_bucket(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    asian = _paper_record(session, match, current_odds=Decimal("1.930"))
    total = _paper_record(
        session,
        match,
        strategy_key="total_goals_hgb_bucket_v2",
        strategy_display_name="大小球 HGB bucket v2",
        model_name="hgb_total_goals",
        market_type="total_goals",
        side="under",
        recommended_handicap="小 2.50",
        original_recommended_handicap="小 2.50",
        line_bucket="mid_2.50",
        risk_tags="line_bucket:mid_2.50,strategy:total_goals_bucket_v2",
        original_market_line=Decimal("2.50"),
        current_market_line=Decimal("2.50"),
        original_odds=Decimal("1.900"),
        current_odds=Decimal("1.900"),
        edge=Decimal("0.1300"),
        scoring_edge=Decimal("0.1300"),
    )
    create_group_snapshots_for_record_ids(
        session,
        [asian.id, total.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    report = build_snapshot_report(session)

    assert report.summary.group_count == 2
    assert "asian_handicap:away_underdog" in report.by_market_line_bucket
    assert "total_goals:mid_2.50" in report.by_market_line_bucket
    assert report.by_market_stake_bucket
    text = format_snapshot_report(report)
    assert "market_type + line_bucket" in text
    assert "asian_handicap:away_underdog" in text
    assert "total_goals:mid_2.50" in text
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py::test_backfill_group_snapshots_marks_historical_backfill tests/test_paper_recommendation_group_snapshot_service.py::test_backfill_group_snapshots_dry_run_does_not_write tests/test_paper_recommendation_group_snapshot_service.py::test_snapshot_report_uses_frozen_stake_and_market_aware_line_bucket -q
```

Expected: FAIL because backfill and report functions do not exist.

- [ ] **Step 3: Implement backfill and report functions**

Append to `src/icewine_prediction/paper_recommendation_group_snapshot_service.py`:

```python
@dataclass(frozen=True)
class SnapshotBackfillResult:
    created_count: int
    candidate_group_count: int
    dry_run: bool


@dataclass(frozen=True)
class SnapshotReportSummary:
    group_count: int
    settled_groups: int
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class SnapshotReportGroup:
    group_name: str
    group_count: int
    settled_groups: int
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class SnapshotReport:
    summary: SnapshotReportSummary
    by_score_bucket: dict[str, SnapshotReportGroup]
    by_stake_bucket: dict[str, SnapshotReportGroup]
    by_market_type: dict[str, SnapshotReportGroup]
    by_side: dict[str, SnapshotReportGroup]
    by_market_stake_bucket: dict[str, SnapshotReportGroup]
    by_market_line_bucket: dict[str, SnapshotReportGroup]
    by_family_combo: dict[str, SnapshotReportGroup]
    by_snapshot_source: dict[str, SnapshotReportGroup]


def backfill_group_snapshots(
    session: Session,
    *,
    from_date: datetime,
    to_date: datetime,
    created_at: datetime,
    snapshot_source: str = "historical_backfill",
    snapshot_version: str = PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    dry_run: bool = False,
) -> SnapshotBackfillResult:
    records = (
        session.query(PaperRecommendationRecord)
        .filter(PaperRecommendationRecord.created_at >= from_date)
        .filter(PaperRecommendationRecord.created_at <= to_date)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    record_ids = [record.id for record in records]
    if dry_run:
        groups = _groups_for_record_ids(session, record_ids)
        return SnapshotBackfillResult(
            created_count=len(groups),
            candidate_group_count=len(groups),
            dry_run=True,
        )
    created = create_group_snapshots_for_record_ids(
        session,
        record_ids,
        snapshot_source=snapshot_source,
        snapshot_version=snapshot_version,
        created_at=created_at,
        is_backfilled=True,
    )
    return SnapshotBackfillResult(
        created_count=len(created),
        candidate_group_count=len(created),
        dry_run=False,
    )


def build_snapshot_report(
    session: Session,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    snapshot_version: str | None = PAPER_CONFIDENCE_SNAPSHOT_VERSION,
) -> SnapshotReport:
    query = session.query(PaperRecommendationGroupSnapshot)
    if from_date is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.created_at >= from_date)
    if to_date is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.created_at <= to_date)
    if snapshot_version is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.snapshot_version == snapshot_version)
    snapshots = query.order_by(PaperRecommendationGroupSnapshot.created_at.asc()).all()
    return SnapshotReport(
        summary=_summarize_snapshots(snapshots),
        by_score_bucket=_group_report(snapshots, _score_bucket),
        by_stake_bucket=_group_report(snapshots, lambda item: str(item.suggested_stake_units)),
        by_market_type=_group_report(snapshots, lambda item: item.market_type),
        by_side=_group_report(snapshots, lambda item: item.side),
        by_market_stake_bucket=_group_report(
            snapshots,
            lambda item: f"{item.market_type}:{item.suggested_stake_units}",
        ),
        by_market_line_bucket=_group_report(
            snapshots,
            lambda item: f"{item.market_type}:{item.line_bucket or 'unknown'}",
        ),
        by_family_combo=_group_report(snapshots, _family_combo),
        by_snapshot_source=_group_report(snapshots, lambda item: item.snapshot_source),
    )


def format_snapshot_report(report: SnapshotReport) -> str:
    return "\n".join(
        [
            _format_snapshot_summary("total", report.summary),
            _format_snapshot_groups("score_bucket", report.by_score_bucket),
            _format_snapshot_groups("stake_bucket", report.by_stake_bucket),
            _format_snapshot_groups("market_type", report.by_market_type),
            _format_snapshot_groups("side", report.by_side),
            _format_snapshot_groups("market_type + stake_bucket", report.by_market_stake_bucket),
            _format_snapshot_groups("market_type + line_bucket", report.by_market_line_bucket),
            _format_snapshot_groups("strategy_family_combo", report.by_family_combo),
            _format_snapshot_groups("snapshot_source", report.by_snapshot_source),
        ]
    )


def _groups_for_record_ids(session: Session, record_ids: list[int]) -> list[PaperConfidenceGroup]:
    if not record_ids:
        return []
    record_id_set = set(record_ids)
    all_records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    workspace = build_paper_confidence_workspace(all_records)
    return [
        group
        for group in workspace.groups
        if record_id_set.intersection(group.signal_record_ids)
    ]


def _summarize_snapshots(snapshots: list[PaperRecommendationGroupSnapshot]) -> SnapshotReportSummary:
    settled = [snapshot for snapshot in snapshots if snapshot.representative_record.status == "settled"]
    flat_profit = sum((_flat_profit(snapshot) for snapshot in settled), Decimal("0")).quantize(MONEY_QUANT)
    weighted_profit = sum((_weighted_profit(snapshot) for snapshot in settled), Decimal("0")).quantize(MONEY_QUANT)
    flat_stake = Decimal(len(settled))
    weighted_stake = sum((snapshot.suggested_stake_units for snapshot in settled), Decimal("0"))
    return SnapshotReportSummary(
        group_count=len(snapshots),
        settled_groups=len(settled),
        flat_profit_units=flat_profit,
        weighted_profit_units=weighted_profit,
        flat_roi=_ratio(flat_profit, flat_stake),
        weighted_roi=_ratio(weighted_profit, weighted_stake),
    )


def _group_report(
    snapshots: list[PaperRecommendationGroupSnapshot],
    key_builder,
) -> dict[str, SnapshotReportGroup]:
    grouped: dict[str, list[PaperRecommendationGroupSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(key_builder(snapshot), []).append(snapshot)
    return {
        key: _report_group(key, group_snapshots)
        for key, group_snapshots in sorted(grouped.items())
    }


def _report_group(
    group_name: str,
    snapshots: list[PaperRecommendationGroupSnapshot],
) -> SnapshotReportGroup:
    summary = _summarize_snapshots(snapshots)
    return SnapshotReportGroup(
        group_name=group_name,
        group_count=summary.group_count,
        settled_groups=summary.settled_groups,
        flat_profit_units=summary.flat_profit_units,
        weighted_profit_units=summary.weighted_profit_units,
        flat_roi=summary.flat_roi,
        weighted_roi=summary.weighted_roi,
    )


def _flat_profit(snapshot: PaperRecommendationGroupSnapshot) -> Decimal:
    profit = snapshot.representative_record.profit_units
    if snapshot.representative_record.status != "settled" or profit is None:
        return Decimal("0.000")
    return profit.quantize(MONEY_QUANT)


def _weighted_profit(snapshot: PaperRecommendationGroupSnapshot) -> Decimal:
    return (_flat_profit(snapshot) * snapshot.suggested_stake_units).quantize(MONEY_QUANT)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / denominator).quantize(Decimal("0.0000"))


def _score_bucket(snapshot: PaperRecommendationGroupSnapshot) -> str:
    score = snapshot.confidence_score
    if score < 55:
        return "<55"
    if score >= 90:
        return "90+"
    lower = score - (score % 5)
    return f"{lower}-{lower + 4}"


def _family_combo(snapshot: PaperRecommendationGroupSnapshot) -> str:
    values = json.loads(snapshot.signal_families_json)
    return "+".join(values) if values else "unknown"


def _format_snapshot_summary(name: str, summary: SnapshotReportSummary) -> str:
    return (
        f"{name}: groups={summary.group_count} settled={summary.settled_groups} "
        f"flat={summary.flat_profit_units} weighted={summary.weighted_profit_units} "
        f"flat_roi={summary.flat_roi} weighted_roi={summary.weighted_roi}"
    )


def _format_snapshot_groups(title: str, groups: dict[str, SnapshotReportGroup]) -> str:
    if not groups:
        return f"{title}: -"
    rows = [
        (
            f"{name} groups={group.group_count} settled={group.settled_groups} "
            f"flat={group.flat_profit_units} weighted={group.weighted_profit_units} "
            f"flat_roi={group.flat_roi} weighted_roi={group.weighted_roi}"
        )
        for name, group in groups.items()
    ]
    return f"{title}: " + " | ".join(rows)
```

- [ ] **Step 4: Run backfill and report tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/icewine_prediction/paper_recommendation_group_snapshot_service.py tests/test_paper_recommendation_group_snapshot_service.py
git commit -m "Add paper snapshot backfill and report"
```

## Task 4: Generate Snapshots From Manual Web Paper Records

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `tests/test_web_console_api.py`

- [ ] **Step 1: Add failing Web API tests**

In `tests/test_web_console_api.py`, add these imports if they are not already present:

```python
from icewine_prediction import web_api
from icewine_prediction.models import League, Match, PaperRecommendationGroupSnapshot, Team
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueRow,
    PaperRecommendationQueueReport,
)
```

Add these local helpers near the existing Web API test helpers:

```python
def _seed_web_snapshot_match(session) -> Match:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country="Japan",
        is_enabled=True,
    )
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Yokohama F. Marinos")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Vissel Kobe")
    match = Match(
        source_name="api-football",
        source_match_id="fixture-snapshot-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 22, 19, 0, tzinfo=BEIJING),
        status="scheduled",
        season=2026,
    )
    session.add_all([league, home, away, match])
    session.commit()
    return match


def _web_snapshot_queue_report(match: Match) -> PaperRecommendationQueueReport:
    row = PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=match.kickoff_time.isoformat(),
        league_name=match.league.name,
        league_display_name="日职联",
        home_team_name=match.home_team.canonical_name,
        home_team_display_name="横滨水手",
        away_team_name=match.away_team.canonical_name,
        away_team_display_name="神户胜利船",
        status="candidate",
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        side="away_cover",
        recommended_handicap="客队 +0.50",
        odds=Decimal("1.930"),
        model_probability=Decimal("0.5600"),
        market_probability=Decimal("0.5100"),
        edge=Decimal("0.1200"),
        line_bucket="away_underdog",
        risk_tags=("line_bucket:away_underdog",),
        scoring_edge=Decimal("0.1200"),
        strategy_key="asian_away_cover_hgb_edge_v1",
        strategy_display_name="亚盘客队方向 HGB edge v1",
        signal_version="v1",
    )
    return PaperRecommendationQueueReport(
        generated_at=datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING).isoformat(),
        window_start=datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING).isoformat(),
        window_end=datetime(2026, 6, 25, 18, 0, tzinfo=BEIJING).isoformat(),
        hours=72,
        near_start_hours=6,
        edge_threshold=Decimal("0.10"),
        model_name="hgb",
        total_matches=1,
        candidate_count=1,
        status_counts={"candidate": 1},
        prefetch_requested=False,
        near_start_fixture_ids=[],
        prefetch_result=None,
        rows=[row],
    )
```

Add tests near existing paper recommendation record API tests:

```python
def test_web_console_api_single_paper_record_creates_group_snapshot(tmp_path, monkeypatch):
    engine = create_database_engine(tmp_path / "web.sqlite3")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        match = _seed_web_snapshot_match(session)
        queue_report = _web_snapshot_queue_report(match)
    monkeypatch.setattr(
        web_api,
        "build_paper_recommendation_queue",
        lambda *args, **kwargs: queue_report,
    )
    app = web_api.create_web_app(
        session_factory=session_factory,
        start_paper_automation_scheduler=False,
        clock=lambda: datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING),
    )
    client = TestClient(app)

    response = client.post(
        "/api/paper-recommendations/records",
        json={"match_id": 1, "strategy_key": "asian_away_cover_hgb_edge_v1"},
    )

    assert response.status_code == 200
    with session_factory() as session:
        assert session.query(PaperRecommendationGroupSnapshot).count() == 1


def test_web_console_api_batch_paper_records_returns_snapshot_ids(tmp_path, monkeypatch):
    engine = create_database_engine(tmp_path / "web.sqlite3")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        match = _seed_web_snapshot_match(session)
        queue_report = _web_snapshot_queue_report(match)
    monkeypatch.setattr(
        web_api,
        "build_paper_recommendation_queue",
        lambda *args, **kwargs: queue_report,
    )
    app = web_api.create_web_app(
        session_factory=session_factory,
        start_paper_automation_scheduler=False,
        clock=lambda: datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING),
    )
    client = TestClient(app)

    response = client.post(
        "/api/paper-recommendations/records/batch",
        json={
            "candidates": [
                {"match_id": 1, "strategy_key": "asian_away_cover_hgb_edge_v1"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch_result"]["snapshot_ids"]
    with session_factory() as session:
        assert session.query(PaperRecommendationGroupSnapshot).count() == 1
```

- [ ] **Step 2: Run failing Web API tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_single_paper_record_creates_group_snapshot tests/test_web_console_api.py::test_web_console_api_batch_paper_records_returns_snapshot_ids -q
```

Expected: FAIL because Web endpoints do not create snapshots.

- [ ] **Step 3: Import snapshot service in Web API**

In `src/icewine_prediction/web_api.py`, add:

```python
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    create_group_snapshots_for_record_ids,
)
```

- [ ] **Step 4: Generate snapshot in single record endpoint**

In `create_paper_recommendation_record`, after `record = create_paper_record_from_queue_row(...)`, add:

```python
                create_group_snapshots_for_record_ids(
                    session,
                    [record.id],
                    snapshot_source="manual_record",
                    created_at=clock(),
                )
```

Leave the response payload unchanged for the single-record endpoint to avoid frontend churn.

- [ ] **Step 5: Generate snapshots in batch endpoint**

In `create_paper_recommendation_records_batch`, initialize:

```python
        created_record_ids: list[int] = []
```

When a record is created, store the id:

```python
                    record = create_paper_record_from_queue_row(
                        session,
                        row,
                        recorded_at=clock(),
                    )
```

Then after successful creation:

```python
                created_record_ids.append(record.id)
```

After the loop and before `clear_cache_prefix`, add:

```python
            snapshot_ids: list[int] = []
            if created_record_ids:
                snapshot_results = create_group_snapshots_for_record_ids(
                    session,
                    created_record_ids,
                    snapshot_source="manual_record",
                    created_at=clock(),
                )
                snapshot_ids = [result.snapshot.id for result in snapshot_results]
```

Add `snapshot_ids` to `workspace_payload["batch_result"]`:

```python
                "snapshot_ids": snapshot_ids,
```

- [ ] **Step 6: Run Web API tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_single_paper_record_creates_group_snapshot tests/test_web_console_api.py::test_web_console_api_batch_paper_records_returns_snapshot_ids -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/icewine_prediction/web_api.py tests/test_web_console_api.py
git commit -m "Create snapshots for manual paper records"
```

## Task 5: Generate Snapshots In Automation And Reuse Generated Groups For Bark

**Files:**
- Modify: `src/icewine_prediction/paper_automation_service.py`
- Modify: `tests/test_paper_automation_service.py`

- [ ] **Step 1: Add failing automation test**

In `tests/test_paper_automation_service.py`, add these imports if they are not already present:

```python
from icewine_prediction.models import PaperAutomationTask, PaperRecommendationGroupSnapshot
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueRow,
    PaperRecommendationQueueReport,
)
```

Add these helpers near existing automation helpers:

```python
def _seed_automation_snapshot_task(session, *, now: datetime) -> PaperAutomationTask:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country="Japan",
        is_enabled=True,
    )
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Yokohama F. Marinos")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Vissel Kobe")
    match = Match(
        source_name="api-football",
        source_match_id="fixture-automation-snapshot-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 22, 19, 0, tzinfo=BEIJING),
        status="scheduled",
        season=2026,
    )
    task = PaperAutomationTask(
        created_at=now,
        updated_at=now,
        created_by="web",
        trigger_at=now,
        match_window_start=match.kickoff_time,
        match_window_end=match.kickoff_time,
        status="running",
        notification_status="pending",
        started_at=now,
    )
    session.add_all([league, home, away, match, task])
    session.commit()
    return task


def _automation_snapshot_queue_report(session, task: PaperAutomationTask) -> PaperRecommendationQueueReport:
    match = (
        session.query(Match)
        .filter(Match.kickoff_time == task.match_window_start)
        .one()
    )
    row = PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=match.kickoff_time.isoformat(),
        league_name=match.league.name,
        league_display_name="日职联",
        home_team_name=match.home_team.canonical_name,
        home_team_display_name="横滨水手",
        away_team_name=match.away_team.canonical_name,
        away_team_display_name="神户胜利船",
        status="candidate",
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        side="away_cover",
        recommended_handicap="客队 +0.50",
        odds=Decimal("1.930"),
        model_probability=Decimal("0.5600"),
        market_probability=Decimal("0.5100"),
        edge=Decimal("0.1200"),
        line_bucket="away_underdog",
        risk_tags=("line_bucket:away_underdog",),
        scoring_edge=Decimal("0.1200"),
        strategy_key="asian_away_cover_hgb_edge_v1",
        strategy_display_name="亚盘客队方向 HGB edge v1",
        signal_version="v1",
    )
    return PaperRecommendationQueueReport(
        generated_at=task.started_at.isoformat(),
        window_start=task.match_window_start.isoformat(),
        window_end=task.match_window_end.isoformat(),
        hours=72,
        near_start_hours=6,
        edge_threshold=Decimal("0.10"),
        model_name="hgb",
        total_matches=1,
        candidate_count=1,
        status_counts={"candidate": 1},
        prefetch_requested=False,
        near_start_fixture_ids=[],
        prefetch_result=None,
        rows=[row],
    )
```

Add a test near existing `execute_paper_automation_task` tests:

```python
def test_execute_task_creates_group_snapshots_and_payload_ids(session):
    now = datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING)
    task = _seed_automation_snapshot_task(session, now=now)
    queue_report = _automation_snapshot_queue_report(session, task)

    result = execute_paper_automation_task(
        session,
        task.id,
        now=now,
        odds_syncer=lambda match_ids: {"success": match_ids, "failed": []},
        queue_builder=lambda session, task: queue_report,
        bark_push_url=None,
    )

    snapshot_ids = result.result_payload["snapshot_ids"]
    assert snapshot_ids
    assert session.query(PaperRecommendationGroupSnapshot).count() == len(snapshot_ids)
    assert result.result_payload["confidence_group_keys"]
```

- [ ] **Step 2: Run failing automation test**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_automation_service.py::test_execute_task_creates_group_snapshots_and_payload_ids -q
```

Expected: FAIL because automation payload has no `snapshot_ids`.

- [ ] **Step 3: Import snapshot service**

In `src/icewine_prediction/paper_automation_service.py`, add:

```python
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    create_group_snapshots_for_record_ids,
)
```

- [ ] **Step 4: Replace direct confidence group lookup with snapshot generation**

In `execute_paper_automation_task`, replace:

```python
        groups = _confidence_groups_for_records(session, created_record_ids)
```

with:

```python
        snapshot_results = create_group_snapshots_for_record_ids(
            session,
            created_record_ids,
            snapshot_source="automation",
            created_at=now,
        )
        groups = [result.group for result in snapshot_results]
        snapshot_ids = [result.snapshot.id for result in snapshot_results]
```

In `result_payload`, add:

```python
            "snapshot_ids": snapshot_ids,
```

Leave `_confidence_groups_for_records` in place for this task. Removing unused helpers is a separate cleanup and is not needed for this feature.

- [ ] **Step 5: Run automation tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_automation_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/icewine_prediction/paper_automation_service.py tests/test_paper_automation_service.py
git commit -m "Create snapshots during paper automation"
```

## Task 6: Add Snapshot Backfill And Report CLI Commands

**Files:**
- Modify: `src/icewine_prediction/cli.py`
- Modify: `tests/test_paper_recommendation_group_snapshot_service.py`

- [ ] **Step 1: Add service-level command behavior tests**

Append one formatting-focused test if not already covered:

```python
def test_format_snapshot_report_includes_market_aware_buckets(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    record = _paper_record(session, match)
    create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    text = format_snapshot_report(build_snapshot_report(session))

    assert "market_type + stake_bucket" in text
    assert "market_type + line_bucket" in text
    assert "asian_handicap:away_underdog" in text
```

- [ ] **Step 2: Run formatting test**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py::test_format_snapshot_report_includes_market_aware_buckets -q
```

Expected: PASS if Task 3 formatting is complete; fix formatting if it fails.

- [ ] **Step 3: Import CLI services**

In `src/icewine_prediction/cli.py`, add:

```python
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    backfill_group_snapshots,
    build_snapshot_report,
    format_snapshot_report,
)
```

- [ ] **Step 4: Add CLI commands under `records_app`**

Add after the existing `@records_app.command("performance")` function:

```python
def _parse_cli_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(f"{value}T00:00:00")


@records_app.command("snapshots-backfill")
def records_snapshots_backfill(
    from_date: str = typer.Option(...),
    to_date: str = typer.Option(...),
    source: str = "historical_backfill",
    version: str = "paper_confidence_v1",
    dry_run: bool = False,
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = backfill_group_snapshots(
            session,
            from_date=_parse_cli_datetime(from_date),
            to_date=_parse_cli_datetime(to_date),
            created_at=datetime.now(tz=ZoneInfo("Asia/Shanghai")),
            snapshot_source=source,
            snapshot_version=version,
            dry_run=dry_run,
        )
    typer.echo(
        "snapshot backfill "
        f"created={result.created_count} "
        f"candidate_groups={result.candidate_group_count} "
        f"dry_run={result.dry_run}"
    )


@records_app.command("snapshot-report")
def records_snapshot_report(
    from_date: str | None = typer.Option(None),
    to_date: str | None = typer.Option(None),
    version: str = "paper_confidence_v1",
):
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_snapshot_report(
            session,
            from_date=_parse_cli_datetime(from_date),
            to_date=_parse_cli_datetime(to_date),
            snapshot_version=version,
        )
    typer.echo(format_snapshot_report(report))
```

- [ ] **Step 5: Run CLI help smoke**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli records snapshots-backfill --help
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli records snapshot-report --help
```

Expected: both commands print help and exit successfully.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/icewine_prediction/cli.py tests/test_paper_recommendation_group_snapshot_service.py
git commit -m "Add paper snapshot CLI commands"
```

## Task 7: Update Memory And Run Final Verification

**Files:**
- Modify: `memory.md`

- [ ] **Step 1: Update project memory**

Add this bullet under `## Stable Decisions` in `memory.md`:

```markdown
- Paper recommendation group snapshots preserve the execution-advice layer for the current paper chain: `paper_recommendation_records` remain the signal facts, while `paper_recommendation_group_snapshots` freeze the grouped confidence score, suggested stake, signal set, source, and version used for later replay. Historical snapshot backfills must be marked as backfilled and not treated as original Web/Bark scores.
```

- [ ] **Step 2: Run focused backend tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest `
  tests/test_database_schema.py `
  tests/test_paper_recommendation_group_snapshot_service.py `
  tests/test_paper_recommendation_tracking_service.py `
  tests/test_paper_automation_service.py `
  tests/test_web_console_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run CLI smoke commands**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli records snapshots-backfill --help
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli records snapshot-report --help
```

Expected: both commands print help and exit successfully.

- [ ] **Step 4: Check git diff for secrets and scope**

Run:

```powershell
git status --short
git diff --stat
rg -n "BARK_PUSH_URL|api.day.app|ODDSPAPI|API_FOOTBALL|SECRET|TOKEN" src tests docs memory.md -g "!docs/superpowers/specs/2026-06-22-paper-recommendation-group-snapshots-design.md"
```

Expected: only intended source/test/docs changes are present; no real secrets are added.

- [ ] **Step 5: Commit verification memory update**

```powershell
git add memory.md
git commit -m "Document paper snapshot tracking decision"
```

When final verification requires source fixes, run the failing focused test again after the fix, then commit the fixed source files and `memory.md` together with:

```powershell
git add src tests memory.md
git commit -m "Verify paper group snapshots"
```

## Self-Review Notes

- Spec coverage: model/schema, snapshot generation, manual records, automation/Bark, historical backfill, snapshot report, market-aware stake/line bucket reporting, and memory handoff are all covered.
- Placeholder scan: no open-ended implementation placeholders should remain in this plan.
- Type consistency: service functions introduced in Task 2 are used by Web and automation tasks; report/backfill functions introduced in Task 3 are used by CLI in Task 6.
