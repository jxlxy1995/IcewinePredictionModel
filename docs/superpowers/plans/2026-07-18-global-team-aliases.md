# Global Team Aliases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every configured or stored team alias available to every odds-source match adapter while preserving source metadata and rejecting ambiguous global mappings.

**Architecture:** Add one shared team-alias loader that merges YAML and database aliases without filtering by `source_name`, normalizes and deduplicates them, and raises on cross-team conflicts. Keep thin `_load_team_aliases` wrappers in both sync runners for compatibility with diagnostics and existing tests, but delegate all loading behavior to the shared service.

**Tech Stack:** Python 3.11+, SQLAlchemy, PyYAML, pytest

---

### Task 1: Shared Global Team Alias Registry

**Files:**
- Create: `src/icewine_prediction/team_alias_service.py`
- Create: `tests/test_team_alias_service.py`

- [ ] **Step 1: Write failing tests for global loading, deduplication, and conflicts**

Create `tests/test_team_alias_service.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.models import ExternalAlias
from icewine_prediction.odds_source_match_service import ExternalAliasInput
from icewine_prediction.team_alias_service import (
    TeamAliasConflictError,
    load_global_team_aliases,
)


def _write_alias_config(tmp_path, lines: list[str]) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(["aliases:", *lines]),
        encoding="utf-8",
    )


def test_load_global_team_aliases_ignores_source_scope(session, tmp_path, monkeypatch):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Ham-Kam",
            "    alias_name: HamKam",
            "  - entity_type: team",
            "    source_name: the_odds_api",
            "    canonical_name: Sichuan Jiuniu",
            "    alias_name: Shenzhen Peng City",
        ],
    )
    monkeypatch.chdir(tmp_path)
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name="another_odds_source",
            canonical_name="Wolves",
            alias_name="Wolverhampton Wanderers",
            normalized_alias="wolverhampton wanderers",
            created_at=datetime(2026, 7, 18, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    session.commit()

    aliases = load_global_team_aliases(session)

    assert ExternalAliasInput("Ham-Kam", "HamKam") in aliases
    assert ExternalAliasInput("Sichuan Jiuniu", "Shenzhen Peng City") in aliases
    assert ExternalAliasInput("Wolves", "Wolverhampton Wanderers") in aliases


def test_load_global_team_aliases_deduplicates_equivalent_records(
    session,
    tmp_path,
    monkeypatch,
):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Ham-Kam",
            "    alias_name: HamKam",
        ],
    )
    monkeypatch.chdir(tmp_path)
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name="the_odds_api",
            canonical_name="Ham-Kam",
            alias_name="HAMKAM",
            normalized_alias="hamkam",
            created_at=datetime(2026, 7, 18, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    session.commit()

    aliases = load_global_team_aliases(session)

    assert aliases == [ExternalAliasInput("Ham-Kam", "HamKam")]


def test_load_global_team_aliases_rejects_cross_team_conflicts(
    session,
    tmp_path,
    monkeypatch,
):
    _write_alias_config(
        tmp_path,
        [
            "  - entity_type: team",
            "    source_name: oddspapi",
            "    canonical_name: Team One",
            "    alias_name: Shared Name",
            "  - entity_type: team",
            "    source_name: the_odds_api",
            "    canonical_name: Team Two",
            "    alias_name: Shared-Name",
        ],
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        TeamAliasConflictError,
        match="shared name.*Team One.*Team Two",
    ):
        load_global_team_aliases(session)
```

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_team_alias_service.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'icewine_prediction.team_alias_service'`.

- [ ] **Step 3: Implement the shared loader**

Create `src/icewine_prediction/team_alias_service.py`:

```python
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from icewine_prediction.alias_service import list_external_aliases, normalize_alias_name
from icewine_prediction.odds_source_match_service import ExternalAliasInput


DEFAULT_TEAM_ALIAS_CONFIG_PATH = Path("config/external_aliases.yaml")


class TeamAliasConflictError(ValueError):
    pass


def load_global_team_aliases(
    session: Session,
    config_path: Path = DEFAULT_TEAM_ALIAS_CONFIG_PATH,
) -> list[ExternalAliasInput]:
    config_aliases = _load_configured_team_aliases(config_path)
    database_aliases = [
        ExternalAliasInput(
            canonical_name=alias.canonical_name,
            alias_name=alias.alias_name,
        )
        for alias in list_external_aliases(session, entity_type="team")
    ]
    return _deduplicate_team_aliases([*config_aliases, *database_aliases])


def _load_configured_team_aliases(config_path: Path) -> list[ExternalAliasInput]:
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    aliases = []
    for item in payload.get("aliases", []):
        if item.get("entity_type") != "team":
            continue
        canonical_name = item.get("canonical_name")
        alias_name = item.get("alias_name")
        if not canonical_name or not alias_name:
            continue
        aliases.append(
            ExternalAliasInput(
                canonical_name=str(canonical_name),
                alias_name=str(alias_name),
            )
        )
    return aliases


def _deduplicate_team_aliases(
    aliases: list[ExternalAliasInput],
) -> list[ExternalAliasInput]:
    aliases_by_normalized_name: dict[str, ExternalAliasInput] = {}
    for alias in aliases:
        normalized_alias = normalize_alias_name(alias.alias_name)
        existing = aliases_by_normalized_name.get(normalized_alias)
        if existing is None:
            aliases_by_normalized_name[normalized_alias] = alias
            continue
        if normalize_alias_name(existing.canonical_name) != normalize_alias_name(
            alias.canonical_name
        ):
            raise TeamAliasConflictError(
                f"team alias conflict for {normalized_alias!r}: "
                f"{existing.canonical_name!r} vs {alias.canonical_name!r}"
            )
    return list(aliases_by_normalized_name.values())
```

- [ ] **Step 4: Run the shared service tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_team_alias_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the shared registry**

```powershell
git add src/icewine_prediction/team_alias_service.py tests/test_team_alias_service.py
git commit -m "增加全局球队别名加载服务"
```

### Task 2: Connect Both Odds Sync Runners

**Files:**
- Modify: `src/icewine_prediction/oddspapi_sync_runner.py:1-30,936-970`
- Modify: `src/icewine_prediction/the_odds_api_sync_runner.py:1-32,720-756`
- Modify: `tests/test_oddspapi_sync_runner.py:921-944`
- Modify: `tests/test_the_odds_api_sync_runner.py:148-188`

- [ ] **Step 1: Change runner tests to require cross-source aliases**

In `tests/test_oddspapi_sync_runner.py`, rename the loader test to `test_load_team_aliases_includes_cross_source_configured_aliases` and change its YAML `source_name` from `oddspapi` to `the_odds_api`. Keep the existing `Dynamo -> FK Dinamo Moscow` assertion.

In `tests/test_the_odds_api_sync_runner.py`, change the final assertion in `test_load_the_odds_api_team_aliases_includes_config_and_database_aliases` to:

```python
    assert ExternalAliasInput(canonical_name="Wolves", alias_name="Wolverhampton Wanderers") in aliases
```

- [ ] **Step 2: Run the two loader tests and confirm both fail**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_oddspapi_sync_runner.py::test_load_team_aliases_includes_cross_source_configured_aliases tests\test_the_odds_api_sync_runner.py::test_load_the_odds_api_team_aliases_includes_config_and_database_aliases -q
```

Expected: both tests fail because each runner still filters aliases by its own source.

- [ ] **Step 3: Delegate runner loading to the shared service**

In both runner modules, remove imports used only by their local YAML loaders: `Path`, `yaml`, and `list_external_aliases`. Add:

```python
from icewine_prediction.team_alias_service import load_global_team_aliases
```

Replace each runner's `_load_team_aliases` and `_load_configured_team_aliases` implementations with the compatibility wrapper:

```python
def _load_team_aliases(session: Session) -> list[ExternalAliasInput]:
    return load_global_team_aliases(session)
```

Keep the wrapper name because `oddspapi_diagnostic_service.py` and existing tests import it.

- [ ] **Step 4: Run both runner test modules**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_oddspapi_sync_runner.py tests\test_the_odds_api_sync_runner.py -q
```

Expected: all tests in both modules pass.

- [ ] **Step 5: Commit the runner integration**

```powershell
git add src/icewine_prediction/oddspapi_sync_runner.py src/icewine_prediction/the_odds_api_sync_runner.py tests/test_oddspapi_sync_runner.py tests/test_the_odds_api_sync_runner.py
git commit -m "让赔率拉取器共享球队别名"
```

### Task 3: Add the Two Match Regressions and Verify

**Files:**
- Modify: `tests/test_the_odds_api_sync_runner.py:97-147`

- [ ] **Step 1: Add a regression test for the provider names observed on 2026-07-18**

Add after the existing external-alias matching test:

```python
def test_find_best_the_odds_api_event_match_handles_reported_global_alias_variants(session):
    cases = [
        (
            "Ham-Kam",
            "Tromso",
            "HamKam",
            "Tromso",
            ExternalAliasInput("Ham-Kam", "HamKam"),
        ),
        (
            "Wuhan Three Towns",
            "Sichuan Jiuniu",
            "Wuhan Three Towns",
            "Shenzhen Peng City FC",
            ExternalAliasInput("Sichuan Jiuniu", "Shenzhen Peng City"),
        ),
    ]

    for index, (home, away, external_home, external_away, alias) in enumerate(cases):
        match = _add_match(session, home_team_name=home, away_team_name=away)
        candidate = find_best_the_odds_api_event_match(
            match,
            [
                {
                    "id": f"event-{index}",
                    "home_team": external_home,
                    "away_team": external_away,
                    "commence_time": "2026-06-26T19:00:00Z",
                }
            ],
            team_aliases=[alias],
        )

        assert candidate is not None
        assert candidate.event_id == f"event-{index}"
        assert candidate.confidence == Decimal("1.0000")
```

- [ ] **Step 2: Run the regression and alias test set**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_alias_service.py tests\test_team_alias_service.py tests\test_oddspapi_sync_runner.py tests\test_the_odds_api_sync_runner.py -q
```

Expected: all selected tests pass, including the two observed match-name variants.

- [ ] **Step 3: Run static and worktree checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` has no output; status lists only the intended regression test and any uncommitted plan/spec documentation.

- [ ] **Step 4: Commit the regressions**

```powershell
git add tests/test_the_odds_api_sync_runner.py
git commit -m "补充球队别名跨源匹配回归测试"
```

- [ ] **Step 5: Confirm the final commit set and clean status**

Run:

```powershell
git log -4 --oneline
git status --short
```

Expected: the global loader, runner integration, and regression commits are present with Chinese messages, and the worktree is clean.
