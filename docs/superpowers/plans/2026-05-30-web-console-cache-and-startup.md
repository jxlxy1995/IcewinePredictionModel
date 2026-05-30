# Web Console Cache And Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web console stop recomputing heavy local database/file data on every open or refresh, keep manual sync results fresh, and provide fixed-port startup scripts.

**Architecture:** Add a small in-process TTL response cache inside the FastAPI app for expensive GET endpoints, with explicit invalidation after POST/PATCH mutations. Reduce initial frontend loading to essential overview data and lazy-load heavier workspaces when their views are opened. Keep Vite and uvicorn on fixed local ports and add one root PowerShell launcher.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, Vite, Vitest, PowerShell.

---

### Task 1: Backend TTL cache and invalidation

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] Add tests proving repeated GETs reuse cached data and sync invalidates match-list cache.
- [ ] Implement a minimal TTL cache with key-prefix invalidation.
- [ ] Wrap expensive GET routes with cache helpers.
- [ ] Clear affected cache entries after display-name saves, match-list syncs, paper-record mutations, and training workflow actions.
- [ ] Run focused backend tests.

### Task 2: Frontend lazy loading

**Files:**
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/apiClient.test.ts`
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] Add tests proving initial dashboard load skips heavy workspaces.
- [ ] Split initial data loading from heavy workspace loading.
- [ ] Load match list, paper tracking, training workspace, display workspace, odds trends, and records only when needed.
- [ ] Preserve manual sync refresh behavior after match-list sync buttons.
- [ ] Run focused frontend tests.

### Task 3: Startup scripts and fixed port

**Files:**
- Modify: `web/vite.config.ts`
- Modify: `scripts/start_web_frontend.ps1`
- Create: `start_web.ps1`

- [ ] Set Vite `strictPort: true`.
- [ ] Make frontend script pass `--host 127.0.0.1 --port 5173`.
- [ ] Add root script that starts backend `127.0.0.1:8000` and frontend `127.0.0.1:5173`.
- [ ] Run build/tests and confirm scripts are syntactically usable.
