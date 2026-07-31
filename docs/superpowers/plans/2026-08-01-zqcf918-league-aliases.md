# zqcf918 League Aliases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Allow zqcf918 automatic match discovery to use source-specific league aliases such as Ekstraklasa (Poland) -> 波兰甲 while preserving the UI name 波兰超.

**Architecture:** Add a focused loader that merges zqcf918 league aliases from YAML and the database, deduplicates them, and rejects ambiguous mappings. Pass those aliases into ZQCF918MatchDiscoverer and add them to its existing raw/display league candidates without changing time or team matching.

**Tech Stack:** Python 3.11+, SQLAlchemy, PyYAML, pytest

---

### Task 1: Load zqcf918 League Aliases

**Files:**
- Create: src/icewine_prediction/league_alias_service.py
- Create: tests/test_league_alias_service.py

- [ ] **Step 1: Write failing loader tests**

Create tests/test_league_alias_service.py. The first test writes a temporary external_aliases.yaml containing:
- a league/zqcf918 row: Ekstraklasa (Poland) -> 波兰甲;
- a league/the_odds_api row that must be ignored;
- a team/zqcf918 row that must be ignored.

Add one database league/zqcf918 alias and one league/the_odds_api alias. Assert only the two zqcf918 league aliases load.

Use this API in the test:

~~~python
from icewine_prediction.league_alias_service import (
    LeagueAliasConflictError,
    load_zqcf918_league_aliases,
)
from icewine_prediction.odds_source_match_service import ExternalAliasInput

aliases = load_zqcf918_league_aliases(session)

assert ExternalAliasInput("Ekstraklasa (Poland)", "波兰甲") in aliases
assert ExternalAliasInput("Ekstraklasa (Poland)", "Ekstraklasa Polska") in aliases
assert ExternalAliasInput("Ekstraklasa (Poland)", "Polish Ekstraklasa") not in aliases
assert ExternalAliasInput("Wolves", "Wolverhampton Wanderers") not in aliases
~~~

The second test supplies equivalent normalized aliases for one canonical league and verifies they deduplicate. It then supplies the same normalized alias for two canonical leagues and asserts LeagueAliasConflictError includes both canonical names.

- [ ] **Step 2: Verify RED**

~~~powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_league_alias_service.py -q
~~~

Expected: ModuleNotFoundError for icewine_prediction.league_alias_service.

- [ ] **Step 3: Implement the loader**

Create src/icewine_prediction/league_alias_service.py with:

~~~python
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from icewine_prediction.alias_service import list_external_aliases, normalize_alias_name
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.odds_source_match_service import ExternalAliasInput


DEFAULT_EXTERNAL_ALIAS_CONFIG_PATH = Path("config/external_aliases.yaml")


class LeagueAliasConflictError(ValueError):
    pass


def load_zqcf918_league_aliases(
    session: Session,
    config_path: Path = DEFAULT_EXTERNAL_ALIAS_CONFIG_PATH,
) -> list[ExternalAliasInput]:
    configured = _load_configured_aliases(config_path)
    database = [
        ExternalAliasInput(alias.canonical_name, alias.alias_name)
        for alias in list_external_aliases(
            session,
            source_name=ZQCF918_SOURCE_NAME,
            entity_type="league",
        )
    ]
    return _deduplicate_aliases([*configured, *database])
~~~

Implement _load_configured_aliases to accept only entity_type=league and source_name=zqcf918 rows with both names. Implement _deduplicate_aliases using normalize_alias_name. If an existing normalized alias has a different normalized canonical name, raise LeagueAliasConflictError with the normalized alias and both canonical names.

- [ ] **Step 4: Verify GREEN and commit**

~~~powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_league_alias_service.py -q
git add src/icewine_prediction/league_alias_service.py tests/test_league_alias_service.py
git commit -m "增加zqcf918联赛别名加载服务"
~~~

Expected: all loader tests pass.

### Task 2: Apply Aliases During Match Discovery

**Files:**
- Modify: src/icewine_prediction/zqcf918_match_service.py
- Modify: tests/test_zqcf918_match_service.py

- [ ] **Step 1: Write the match 19824 regression**

Add imports for DisplayNameService, ExternalAliasInput, and _match_candidates. Add this test:

~~~python
def test_match_candidates_uses_zqcf918_league_alias_without_changing_display_name(session):
    match = _add_match(
        session,
        league_name="Ekstraklasa (Poland)",
        home_name="Wisla Plock",
        away_name="Widzew Łódź",
        kickoff_time=datetime(2026, 8, 1, 0, 0),
    )
    candidate = {
        "ID": "4559263",
        "league": "波兰甲",
        "home": "华沙普洛克",
        "away": "维德祖罗兹",
        "time": "2026-08-01 00:00:00",
    }
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Ekstraklasa (Poland)": "波兰超"},
            teams={"Wisla Plock": "华沙普洛克", "Widzew Łódź": "维德祖罗兹"},
        )
    )

    assert _match_candidates(
        [match], [candidate], display_service=display_service
    ) == {}
    assert _match_candidates(
        [match],
        [candidate],
        display_service=display_service,
        league_aliases=[ExternalAliasInput("Ekstraklasa (Poland)", "波兰甲")],
    ) == {match.id: "4559263"}
~~~

- [ ] **Step 2: Verify RED**

~~~powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_zqcf918_match_service.py::test_match_candidates_uses_zqcf918_league_alias_without_changing_display_name -q
~~~

Expected: failure because _match_candidates does not accept league_aliases.

- [ ] **Step 3: Extend discoverer and matcher**

Add league_aliases: list[ExternalAliasInput] | None = None to ZQCF918MatchDiscoverer.__init__, store an empty-list default, and pass it to both current and finished _match_candidates calls.

Extend the matcher API:

~~~python
def _match_candidates(
    matches: list[Match],
    candidates: list[dict[str, Any]],
    *,
    display_service: DisplayNameService,
    league_aliases: list[ExternalAliasInput] | None = None,
) -> dict[int, str]:
    ...
    league_names = _league_name_candidates(
        match.league.name,
        display_service,
        league_aliases=league_aliases or [],
    )


def _league_name_candidates(
    name: str,
    display_service: DisplayNameService,
    *,
    league_aliases: list[ExternalAliasInput],
) -> list[str]:
    values = [name, display_service.display_league(name)]
    values.extend(
        alias.alias_name for alias in league_aliases if alias.canonical_name == name
    )
    return list(dict.fromkeys(_normalized_team(value) for value in values if value))
~~~

- [ ] **Step 4: Verify GREEN and commit**

~~~powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_zqcf918_match_service.py -q
git add src/icewine_prediction/zqcf918_match_service.py tests/test_zqcf918_match_service.py
git commit -m "支持zqcf918联赛别名匹配"
~~~

Expected: all match-service tests pass.

### Task 3: Wire Default Sync and Add Production Configuration

**Files:**
- Modify: src/icewine_prediction/zqcf918_match_service.py
- Modify: config/external_aliases.yaml
- Modify: tests/test_zqcf918_match_service.py

- [ ] **Step 1: Write a failing wiring test**

In a temporary working directory, create external_aliases.yaml with the Ekstraklasa zqcf918 league alias. Monkeypatch ZQCF918MatchDiscoverer with a fake constructor that captures league_aliases and whose discover returns an empty mapping. Call sync_zqcf918_match_ids_for_matches for a missing mapping and assert the captured aliases equal:

~~~python
[ExternalAliasInput("Ekstraklasa (Poland)", "波兰甲")]
~~~

Expected before implementation: the fake receives no league_aliases keyword.

- [ ] **Step 2: Wire the default discoverer**

Import load_zqcf918_league_aliases and change only the default path:

~~~python
discoverer = discoverer or ZQCF918MatchDiscoverer(
    league_aliases=load_zqcf918_league_aliases(session),
)
~~~

Explicitly supplied discoverers must remain untouched.

- [ ] **Step 3: Add production alias**

Append under aliases in config/external_aliases.yaml:

~~~yaml
  - entity_type: league
    source_name: zqcf918
    canonical_name: Ekstraklasa (Poland)
    alias_name: 波兰甲
~~~

Do not modify config/display_names.yaml.

- [ ] **Step 4: Run focused tests and commit**

~~~powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_league_alias_service.py tests\test_zqcf918_match_service.py tests\test_zqcf918_sync_service.py -q
git add src/icewine_prediction/zqcf918_match_service.py config/external_aliases.yaml tests/test_zqcf918_match_service.py
git commit -m "补充zqcf918波兰联赛别名"
~~~

Expected: all selected tests pass without external API calls.

### Task 4: Final Verification

- [ ] **Step 1: Run all tests**

~~~powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest -q
~~~

Expected: zero failures. Report existing sklearn and FastAPI warnings if present.

- [ ] **Step 2: Check scope**

~~~powershell
git diff --check HEAD~3..HEAD
git status --short
rg -n -C 2 'canonical_name: Ekstraklasa \(Poland\)|alias_name: 波兰甲' config/external_aliases.yaml
~~~

Expected: no whitespace errors; the feature commits contain only intended files; the pre-existing config/display_names.yaml change remains unstaged and outside all feature commits.

- [ ] **Step 3: Report evidence**

Report focused and full test counts, warnings, commits, and that tests made no external odds request or database write.
