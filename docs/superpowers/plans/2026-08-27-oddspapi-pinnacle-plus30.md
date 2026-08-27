# Oddspapi Pinnacle +30 Slug 适配实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Oddspapi v4 请求使用账号实际授权的 `pinnacle+30` bookmaker slug，同时把响应归一化为项目现有的内部 bookmaker `pinnacle`。

**Architecture:** 在 Oddspapi 适配层增加供应商 slug 与内部名称之间的单向转换，不修改数据库字段、模型特征或其他赔率源。默认同步参数仍保留内部名称 `pinnacle`，请求发送前转换为 `pinnacle+30`，响应映射前转换回 `pinnacle`；其他显式 bookmaker（例如历史工具使用的 `sbobet`）保持原行为。

**Tech Stack:** Python, requests, SQLAlchemy, pytest, PowerShell CLI。

---

### Task 1: 建立 bookmaker slug 转换模块和单元测试

**Files:**
- Create: `src/icewine_prediction/sources/oddspapi_bookmaker.py`
- Create: `tests/test_oddspapi_bookmaker.py`

- [x] **Step 1: Write the failing tests**

```python
from icewine_prediction.sources.oddspapi_bookmaker import (
    normalize_bookmaker_slug,
    to_api_bookmaker_slug,
)


def test_internal_pinnacle_uses_pinnacle_plus_30_api_slug():
    assert to_api_bookmaker_slug("pinnacle") == "pinnacle+30"


def test_other_explicit_bookmakers_are_unchanged():
    assert to_api_bookmaker_slug("sbobet") == "sbobet"


def test_pinnacle_plus_30_is_normalized_to_existing_internal_name():
    assert normalize_bookmaker_slug("pinnacle+30") == "pinnacle"


def test_unknown_slug_is_lowercased_without_conflation():
    assert normalize_bookmaker_slug("ExampleBook") == "examplebook"
```

- [x] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_oddspapi_bookmaker.py -q
```

Expected: collection failure because `oddspapi_bookmaker.py` does not exist yet.

- [x] **Step 3: Implement the conversion functions**

```python
PINNACLE_INTERNAL_BOOKMAKER = "pinnacle"
PINNACLE_API_BOOKMAKER = "pinnacle+30"


def to_api_bookmaker_slug(bookmaker: str) -> str:
    slug = str(bookmaker).strip().lower()
    if slug == PINNACLE_INTERNAL_BOOKMAKER:
        return PINNACLE_API_BOOKMAKER
    return slug


def normalize_bookmaker_slug(bookmaker: str) -> str:
    slug = str(bookmaker).strip().lower()
    if slug == PINNACLE_API_BOOKMAKER:
        return PINNACLE_INTERNAL_BOOKMAKER
    return slug
```

- [x] **Step 4: Run the test and verify it passes**

Run the command from Step 2. Expected: `4 passed`.

- [x] **Step 5: Commit the focused module**

```powershell
git add src/icewine_prediction/sources/oddspapi_bookmaker.py tests/test_oddspapi_bookmaker.py
git commit -m "增加Oddspapi Pinnacle加30秒标识转换"
```

### Task 2: 将请求和响应映射接入转换层

**Files:**
- Modify: `src/icewine_prediction/oddspapi_sync_runner.py:29-45,278-286,317-328`
- Modify: `src/icewine_prediction/sources/oddspapi_odds_mapper.py:1-120`
- Modify: `tests/test_oddspapi_sync_runner.py`
- Modify: `tests/test_oddspapi_odds_mapper.py`

- [x] **Step 1: Add failing request and response tests**

Add runner assertions whose fake client records both `fetch_historical_odds()` and `fetch_markets()` parameters and assert the default requests contain `"bookmakers": "pinnacle+30"`. Add nested and flat mapper cases with source bookmaker `pinnacle+30`, asserting every mapped snapshot has `bookmaker == "pinnacle"`. Keep an explicit `bookmaker="sbobet"` test asserting it remains `sbobet`.

- [x] **Step 2: Run the focused tests and confirm the old behavior fails**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_oddspapi_sync_runner.py tests/test_oddspapi_odds_mapper.py -q
```

Expected: the new request assertion sees `pinnacle`, and the mapper test returns no rows for `pinnacle+30`.

- [x] **Step 3: Convert only the outgoing API parameter**

Import `to_api_bookmaker_slug` and change both `fetch_historical_odds()` and `fetch_markets()` so their request parameters remain structurally unchanged except for the outgoing slug:

```python
params = {
    "sportId": SOCCER_SPORT_ID,
    "fixtureId": source_fixture_id,
    "bookmakers": to_api_bookmaker_slug(self.bookmaker),
}
```

Use the same converted value in the `markets` request. Keep the market-definition cache key based on `self.bookmaker` (the internal name), so `pinnacle` and `pinnacle+30` cannot create duplicate internal caches.

Do not change `DEFAULT_BOOKMAKER = "pinnacle"`; it is the internal name used by callers and existing data contracts.

- [x] **Step 4: Normalize before filtering and storing mapped rows**

In both `_map_flat_historical_odds()` and `_map_nested_historical_odds()`, normalize the source slug before comparing it to the whitelist and before constructing `MappedHistoricalOddsSnapshot`. Normalize the whitelist once at the entry point so either `pinnacle` or `pinnacle+30` passed by a caller selects the same rows:

```python
bookmaker_whitelist = {
    normalize_bookmaker_slug(value)
    for value in (selected_bookmakers or SELECTED_BOOKMAKERS)
}
```

The stored `bookmaker` field must therefore remain `pinnacle`, while raw payloads can retain the provider's original `pinnacle+30` key.

- [x] **Step 5: Run the focused tests and the complete Oddspapi suite**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_oddspapi_bookmaker.py tests/test_oddspapi_client.py tests/test_oddspapi_odds_mapper.py tests/test_oddspapi_sync_runner.py tests/test_oddspapi_diagnostic_service.py -q
```

Expected: all selected tests pass, including existing `pinnacle` and `sbobet` compatibility assertions.

- [x] **Step 6: Commit the adapter integration**

```powershell
git add src/icewine_prediction/oddspapi_sync_runner.py src/icewine_prediction/sources/oddspapi_odds_mapper.py tests/test_oddspapi_sync_runner.py tests/test_oddspapi_odds_mapper.py
git commit -m "适配Oddspapi Pinnacle加30秒请求与入库名称"
```

### Task 3: 做一次无持久化真实接口验证

**Files:**
- Temporary: `.tmp/oddspapi-pinnacle-plus30-probe-20260827.sqlite3` (gitignored)

- [x] **Step 1: Keep automatic Oddspapi sync disabled during validation**

Leave `config/sync.yaml` unchanged with `oddspapi_enabled: false`. Do not alter the formal database or the user's unrelated `备用key.txt`.

- [x] **Step 2: Probe the known fixture through the adapted request path**

Use fixture `id1000002267018124` (matchID `17816`) with the existing client and a temporary database/session. Verify the prepared request URL contains `bookmakers=pinnacle%2B30`, HTTP status is `200`, and the response bookmaker key is `pinnacle+30`. Do not call the persistence functions against `local_data/icewine_prediction.sqlite3`.

- [x] **Step 3: Verify normalization and no data-contract drift**

Assert the mapped result has non-zero rows, every row has `source_name == "oddspapi"` and `bookmaker == "pinnacle"`, and no new `pinnacle+30` bookmaker value is written to the temporary or formal schema.

- [x] **Step 4: Remove only the temporary probe database and inspect status**

```powershell
Remove-Item -LiteralPath .tmp/oddspapi-pinnacle-plus30-probe-20260827.sqlite3 -ErrorAction SilentlyContinue
git diff --check
git status --short
```

Expected: only the planned source/test changes are present; `备用key.txt` remains untouched and unstaged.

### Task 4: 小范围启用与回滚

**Files:**
- Modify: `config/sync.yaml:6`
- Modify: `docs/superpowers/plans/2026-08-27-oddspapi-pinnacle-plus30.md`

- [x] **Step 1: Enable only after the real probe passes**

Change exactly one setting:

```yaml
oddspapi_enabled: true
```

Restart the backend/worker and run one or two known matches with a small request budget. Confirm logs show the adapted request and that inserted rows use `bookmaker=pinnacle`.

- [x] **Step 2: Verify the provider chain remains intact**

For a match where Oddspapi succeeds, confirm later The Odds API and zqcf918 calls are not made. For a deliberately unavailable match, confirm fallback still proceeds to The Odds API and then zqcf918 as before.

- [x] **Step 3: Record rollback procedure**

If the real run fails, set `oddspapi_enabled: false`, restart the service, and leave all already stored rows untouched. This restores the current `The Odds API → zqcf918` chain without reverting the adapter code.

- [x] **Step 4: Run the final verification set**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_oddspapi_bookmaker.py tests/test_oddspapi_client.py tests/test_oddspapi_odds_mapper.py tests/test_oddspapi_sync_runner.py tests/test_match_odds_sync_service.py -q
```

Expected: all tests pass; no database migration is required.
