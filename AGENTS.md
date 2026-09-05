# AGENTS.md

## Project purpose

`npc-smallville-sim` is an installable generative NPC simulation server: a generative-agent-style
memory + observation + action loop, backed by a local LLM (Ollama by default, or an
OpenAI-compatible llama.cpp server), with a real-time dashboard, REST/WebSocket APIs, JS/Java
client libraries, and an on-device Android port (Chaquopy + bundled llama.cpp).

## Architecture

- `backend/` — Python FastAPI application (the only Python package, `backend`).
  - `server.py` — `app` (FastAPI), all routes (`/api/*` and `/ws/events`, incl. the `/api/health`
    readiness probe, plus Smallville-compatible `/state`, `/agents`, `/locations`, `/objects`,
    `/react`), CORS, sliding-window rate limiter,
    `npc-sim` entry point (`main()` runs uvicorn on `0.0.0.0:8000`). Creates the module-level
    `engine = SimulationEngine()` singleton at import time.
  - `engine.py` — `SimulationEngine`: tick loop, seeded world/agents, memory retention (capped at
    `MAX_MEMORIES`), decision policy, WebSocket `subscriptions`/`broadcast`, god interventions,
    conversations.
  - `llm.py` — `LLMClient`, thin async HTTP client for both providers: Ollama
    (`/api/generate`, `/api/tags`) and OpenAI-compatible (`/v1/chat/completions`, `/v1/models`).
    Every LLM failure returns `None`/`{}` and the engine falls back to a heuristic policy.
  - `models.py` — dataclasses for internal state (`Agent`, `Memory`, `WorldLocation`,
    `WorldObject`, `Conversation`) and pydantic request models.
  - `dashboard/` — plain JS/CSS/HTML dashboard, served as static files and packaged as package
    data (`backend = ["dashboard/*"]` in `pyproject.toml`); must be kept in sync if files change.
- `tests/` — pytest using FastAPI `TestClient`.
- `clients/javascript/` — ESM client (`src/index.js`, no build step, zero deps).
- `clients/java/` — Maven client (`pom.xml`, Java 17), returns raw JSON strings.
- `android/` — Gradle project (AGP 8.5.2 + Chaquopy 17). Embeds `backend/` as a Python source
  dir; `MainActivity` boots a bundled llama.cpp server (port 8080, OpenAI-compatible) then runs
  `npc_android.start_server()` (uvicorn on 127.0.0.1:8000).
- `Dockerfile`, `docker-compose.yml`, `run_all_in_one.sh`, `run_all_in_one_windows.bat` —
  Docker deployment (ollama + sim services).

## Entry points

- Console script: `npc-sim` → `backend.server:main` (defined in `pyproject.toml`).
- `python -m backend.server` runs the same `main()`.
- Docker: `sim` service `CMD ["npc-sim"]`.
- Tests import `backend.server.app` directly.
- Android boot flow: `android/app/src/main/java/com/npcsmallville/sim/MainActivity.java`, then
  `android/app/src/main/python/npc_android.py`.

## Build / run

- Docker stack (default): `./run_all_in_one.sh` (Linux/macOS) or `run_all_in_one_windows.bat`
  (Windows). Dashboard at `http://localhost:8000`, Ollama at `http://localhost:11434`.
- Local install: `pip install .` then `npc-sim`.
- Dev/editable install: `pip install -e ".[dev]"`.
- Run server directly: `.venv/bin/python -m backend.server` (uvicorn on port 8000).
- Set tuning env vars (`OLLAMA_MODEL`, `SIM_TICK_SECONDS`, `MAX_MEMORIES`) before startup.

## Test

- `pytest` (testpaths `tests`, default `-q`). CI runs `pytest -v`.
- Tests hit the real API through `TestClient` via the autouse `fresh_engine` fixture in
  `tests/conftest.py`, which swaps a freshly constructed `SimulationEngine` into
  `backend.server.engine` per test. Keep using that fixture — a bare constructor does not reset
  the engine the routes/WebSocket use, so state leaks between tests.
- Tests must pass with no LLM/Ollama reachable — the engine's fallback decision policy keeps
  behavior deterministic when the model is unavailable.

## Lint / type check

- `ruff check .` — line-length 120, `E`/`F`/`W`/`I`/`UP`/`B` selected, `E501` ignored. No formatter
  is configured (no `ruff format`, no black/isort); match `.editorconfig`
  (4-space Python, 2-space JS/HTML/CSS/JSON/YAML/bat).
- `mypy backend` — target `python_version = "3.10"`, `ignore_missing_imports`,
  `check_untyped_defs`.
- CI gate (`.github/workflows/ci.yml`, Python 3.12): `ruff check .` → `mypy backend` → `pytest -v`.
  CI covers only the Python backend — there are no CI steps for `clients/` (JS/Java) or `android/`.

## Dependency management

- `pyproject.toml` is the source of truth (setuptools). Runtime deps are pinned:
  `fastapi==0.115.0`, `uvicorn[standard]==0.30.6`, `httpx==0.27.2`. `requires-python = ">=3.10"`.
  Dev tools (`pytest`, `ruff`, `mypy`) live in `[project.optional-dependencies].dev`.
- `requirements.txt` must mirror the pinned runtime deps; `requirements-dev.txt` = runtime + dev
  tools. When bumping versions, update `pyproject.toml` AND `requirements.txt` together.
- Docker builds via `pip install .`, so `pyproject.toml` is authoritative for the container.
- Android (Chaquopy `pip` block in `android/app/build.gradle`) uses a separate, older pin set
  (`fastapi==0.100.1`, `pydantic<2`, `anyio==3.7.1`) — keep it compatible when bumping backend deps.

## Coding conventions

- Backend-package modules start with `from __future__ import annotations`; use builtin generics
  (`dict[str, ...]`, `list[...]`) and `str | None` unions (≥3.10 only — no 3.12-only syntax).
- Module-level logger via `logging.getLogger("npc_sim.<module>")`; log through `log.*` helpers.
- Request bodies are pydantic `BaseModel`; internal simulation state is `dataclass`.
- LLM-triggering endpoints add `dependencies=[Depends(llm_rate_limit)]` (429 on excess).
- `except Exception` with `# noqa: BLE001` at the LLM/broadcast boundary is intentional
  (graceful degradation) — do not "tighten" it without changing the fallback behavior.
- The dashboard (`backend/dashboard/app.js`) renders agent/LLM-derived text with
  `textContent`/`setText`, never `innerHTML` (stored-XSS guard) — keep new UI code on that pattern.

## Naming conventions

- Env vars use the `SIM_` prefix (`SIM_TICK_SECONDS`, `SIM_LLM_*`, `SIM_RELOAD`,
  `SIM_LOG_LEVEL`, `SIM_CORS_*`, `SIM_RATE_LIMIT_RPM`). `OLLAMA_URL`/`OLLAMA_MODEL` are legacy
  aliases honored when the `SIM_LLM_URL`/`SIM_LLM_MODEL` equivalents are unset; `MAX_MEMORIES`
  is a legacy-suffixed tuning knob.
- Agent IDs are auto-generated `a{len(agents)+1}`; seeded agents are `a1`-`a3` (Maya, Sam, Iris).
- Memory `source` values: `init`, `seed`, `observation`, `decision`, `dialogue`,
  `external_observation`, `god_intervention`.
- The LLM decision contract (in `engine._decide_next_action`) is compact JSON with keys exactly
  `action`, `mood`, `reason`; `format_json` is set when calling the LLM. Keep it stable — both
  `llm.py` (`JSON_PROMPT`) and `engine.py` describe it.

## Important environment variables

- `OLLAMA_MODEL` (default `tinyllama:1.1b`) — model name; fallback for `SIM_LLM_MODEL`.
- `OLLAMA_URL` (default `http://ollama:11434` in Docker) — fallback for `SIM_LLM_URL`.
- `SIM_TICK_SECONDS` (default `8`), `MAX_MEMORIES` (default `48`) — simulation tuning.
- `SIM_LLM_PROVIDER` (`ollama`|`openai`), `SIM_LLM_URL`, `SIM_LLM_MODEL`, `SIM_LLM_TIMEOUT`
  (`15`) — provider override; provider defaults to `openai` on Android, `ollama` elsewhere.
- `SIM_RELOAD` (`true` enables uvicorn reload), `SIM_LOG_LEVEL` (default `info`).
- `SIM_CORS_ORIGINS` (default `*`), `SIM_CORS_CREDENTIALS` (default `false`) — credentials cannot
  be combined with a wildcard origin; set explicit origins if you enable credentials.
- `SIM_RATE_LIMIT_RPM` (default `120`; `<=0` disables).
- Environment must be set BEFORE importing `backend.server` (env is read at module import time on
  the module-level singleton).

## Files/directories that should not normally be modified

- `android/local.properties` and `android/gradle.properties` — machine-specific SDK/aapt2 paths
  (this environment's proot/arm64 hacks); values are environment-specific, not project config.
- Build artifacts / caches: `.venv/`, `npc_smallville_sim.egg-info/`, `__pycache__/`,
  `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`.
- `backend/dashboard/` static assets are packaged via package-data; if you add files there, keep
  `pyproject.toml`'s `backend = ["dashboard/*"]` in sync.

## Git conventions

- Remote is `origin` → `git@github.com:Narrator-exe/game.git`; work on `main`. PRs are merged
  into `main` (branch names historically `codex/<feature>` / `Narrator-exe/<feature>`).
- Commit subjects are short, imperative, plain-English one-liners
  (e.g. "Add god intervention panel and API for informing agents").

## Verification requirements

Before considering a change done, run (from repo root, in `.venv`):

```
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/pytest -v
```

## Common pitfalls

- `POST /api/interventions` expects `{"message", "mode": "all|single|multiple", "agent_ids"}`
  (`GodInterventionRequest` in `backend/models.py`). README documents a `content`/`target_agent_id`
  payload — trust the code, not the README.
- `run_all_in_one_windows.bat` calls the legacy `docker-compose` CLI while `run_all_in_one.sh`
  uses `docker compose`; keep both working when editing the launchers.
- Do not add LLM/Ollama tests or require a model to be running — tests and CI assume the LLM is
  unavailable and exercise the fallback policy.
- Rate limiter is a module-level singleton shared across requests; hammering LLM endpoints
  (e.g. `POST /api/agents/{id}/ask`, `/api/sim/tick`, `/state`) can return 429 during a test run.
- Memory retention truncates to the newest `MAX_MEMORIES` after every `_remember`; long-form tests
  must not assume unbounded memory growth.
- The Android app is not self-contained in the repo: there is no `gradlew` wrapper, so the
  README's `./gradlew assembleDebug` does not run as-is, and there is no
  `android/app/src/main/assets/` with the `llama-server` binary or `model.gguf` — those are
  built/cross-compiled outside the repo (see README's `/opt/llama/android-toolchain.cmake` note).
  `MainActivity` extracts them from `assets/` at runtime, so the boot flow fails until they exist.
- Keep `requirements.txt` pins in lock-step with `pyproject.toml`; keeping them in sync is part of
  every dependency change.