# AGENTS.md

Local rules for the Python data-pipeline engine.

## Commands

```powershell
py -3.11 -m venv .venv
$env:PYTHONUTF8="1"
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m acceptance_runbook
$env:DATABASE_URL="postgresql+asyncpg://caishui:localdev_password@127.0.0.1:55432/caishui_db"; $env:PIPELINE_SHARED_SECRET="local-smoke-secret"; .\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Pipeline tests must run from `data-pipeline/` under `.venv`, not global Anaconda/Python. Validated local stack: Python `3.11.9`, pytest `8.2.2`, pytest-asyncio `0.23.7`.

Set `PYTHONUTF8=1` on Windows when installing or running commands that may touch UTF-8 files.

When starting FastAPI for WebApp/UI validation on Windows, set `DATABASE_URL`, `PIPELINE_SHARED_SECRET`, `PYTHONUTF8`, and provider env in the current PowerShell process before `Start-Process`, then let `.venv\Scripts\python.exe` inherit that environment. Do not wrap those assignments inside a nested `powershell -Command` string; quote loss can make values such as `postgresql+asyncpg://...`, `local-smoke-secret`, or provider keys execute as commands, leaving the app without required env.

If startup logs are redirected for diagnosis, keep them outside the repository, read only the relevant startup error, then delete them immediately because they may contain env-derived secrets. Cleanup must stop only the known Pipeline PID or the exact `8000` port owner, never broad `python` process names.

## Dependency Compatibility

- Keep `openai==1.35.13` paired with `httpx==0.27.2`.
- `httpx 0.28+` removes the legacy `proxies` argument used by this OpenAI SDK version and breaks `AsyncOpenAI(...)` construction.

## Owning Modules

- `ingestion.py` owns Source Document ingestion orchestration: load -> chunk -> enrich metadata -> reconcile lifecycle -> verify -> persist.
- `chunk_lifecycle.py` owns preserving/replacing chunk row state across reprocessing.
- `acceptance_runbook.py` owns pipeline final local acceptance order and environment anti-misuse guidance.
- `output/schemas.py` is the Pydantic half of the cross-engine JSON contract.
- `db/models.py` mirrors Prisma-owned tables for reads/writes only.

## Database Ownership

- Do not introduce Alembic.
- Do not call SQLAlchemy `create_all`.
- Pipeline may read/write existing Prisma-owned tables; Prisma remains the sole DDL owner.
- `ingest_tasks.document_id` must reference an existing WebApp-owned `source_documents` row.

## Contract Rules

- `output/schemas.py` must stay structurally mirrored with `caishui-webapp/types/pipeline.ts`.
- Closed TypeScript unions/Zod enums must be closed Pydantic `Literal[...]` or strict enums.
- Do not loosen contract fields to plain `str`, `dict`, or `Any`.
- Pipeline wire doc types are lowercase: `regulation`, `announcement`, `notice`, `interpretation`, `case`, `guide`.

## Test Runner Drift

- Keep `pythonpath = ["."]` in project config for the flat layout.
- Do not fix imports with ad hoc `sys.path.append(...)`.
- Do not remove `asyncio_mode = "auto"` to silence warnings caused by missing pytest-asyncio; install locked dependencies instead.
