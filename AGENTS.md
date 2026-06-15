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
- `transformers/chunker.py` owns semantic chunk boundaries and provider-safe maximum chunk length.
- `chunk_lifecycle.py` owns preserving/replacing chunk row state across reprocessing.
- `acceptance_runbook.py` owns pipeline final local acceptance order and environment anti-misuse guidance.
- `output/schemas.py` is the Pydantic half of the cross-engine JSON contract.
- `db/models.py` mirrors Prisma-owned tables for reads/writes only.

## Chunking and Embedding Safety

- Text chunks must be capped before embedding. Do not allow a normal text chunk to exceed `MAX_CHUNK_TOKENS`, even when source text has no punctuation, clause boundaries are missing, many short clauses/paragraphs accumulate in `pending`, or a short heading is merged into a pending chunk.
- Provider `400 invalid parameter` errors caused by oversized chunk input are pipeline bugs, not acceptable runtime filtering.
- Table chunks may preserve table integrity, but any future table-size exception must be explicit, tested, and reflected in retrieval-readiness behavior.

## Seed Verification Path

- `verification_method="seed"` is the trusted official-source auto-verification path used by WebApp admin uploads.
- Seed verification is chunk-level: each generated chunk must still pass structural preparation and then be marked `verified` with `verification_method="seed"` and audit-relevant seed metadata.
- Missing `doc_number` and provider-safe sentence-boundary cuts are not seed blockers. Some authoritative regulations have no document number, and chunking may end near punctuation to satisfy model input limits.
- Seed blockers should be core quality failures such as too-short content, missing source location, missing issuing body, or missing effective date.
- Human review remains available for exceptions, rejected/failed chunks, and spot checks; it is not the normal path for every trusted official import.

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
