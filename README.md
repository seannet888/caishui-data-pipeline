# Caishui Data Pipeline

财税知识库数据清洗服务。该服务负责把上传文件解析为可信的 Knowledge Chunks，并按 v2.1 架构规则执行元数据抽取、chunk 生命周期处理、seed/human verification 标记、verified-only embedding，以及写入共享 PostgreSQL。

当前仓库是 `caishui-webapp` 的配套 Pipeline Service，但代码边界独立：WebApp 负责 Prisma schema、数据库迁移、检索、问答和引用审计；Pipeline 只负责数据清洗与入库执行。

## Responsibilities

- Load PDF / Markdown / Excel / CSV source files.
- Split source documents into stable chunks.
- Extract tax metadata by deterministic rules.
- Preserve chunk lifecycle across reprocessing.
- Verify chunks through `seed` or `human` workflows.
- Generate production embeddings only for `verified` chunks.
- Write ingestion progress and chunks to the shared PostgreSQL database.
- Expose preview, ingest, and task-status APIs.

## Non-goals

- This service does not own database migrations.
- This service must not run Alembic or SQLAlchemy `create_all`.
- This service does not perform retrieval, answer generation, citation finalization, or user-facing Q&A.
- This service does not implement `verification_method = "auto"` in MVP.

## Runtime

- Python `3.11.x`
- FastAPI `0.111.x`
- Pydantic v2
- PostgreSQL is shared with `caishui-webapp`
- Embeddings use SiliconFlow OpenAI-compatible API:
  - model: `BAAI/bge-large-zh-v1.5`
  - dimension: `1024`

Important dependency compatibility:

- `openai==1.35.13`
- `httpx==0.27.2`

Do not upgrade `httpx` to `0.28+` while `openai==1.35.13` is pinned. OpenAI SDK 1.35.x still passes the legacy `proxies` argument to httpx.

## Local Setup

PowerShell:

```powershell
py -3.11 -m venv .venv
$env:PYTHONUTF8="1"
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Create local environment config:

```powershell
Copy-Item .env.example .env
```

Then fill:

- `DATABASE_URL`
- `PIPELINE_SHARED_SECRET`
- `EMBEDDING_API_KEY`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSION`

## Run

```powershell
$env:PYTHONUTF8="1"
.\.venv\Scripts\python -m uvicorn api.main:app --reload
```

Default local URL:

```text
http://localhost:8000
```

Health check:

```text
GET /health
```

## Test

```powershell
$env:PYTHONUTF8="1"
.\.venv\Scripts\python -m pytest
```

Expected baseline as of 2026-06-12:

```text
33 passed, 1 skipped
```

## API

All operational endpoints require Pipeline Trust signing through shared-secret headers. The WebApp is expected to sign calls using the same `PIPELINE_SHARED_SECRET`.

### `POST /preview`

Runs the real loader, chunker, and metadata extraction path without verification, embedding, or database writes.

Use this for upload preview and chunk inspection.

Returns:

```text
PipelineOutput
```

### `POST /ingest`

Persists the uploaded source file, creates an ingest task, and runs ingestion in a FastAPI `BackgroundTasks` worker.

Returns:

```json
{
  "task_id": "...",
  "document_id": "...",
  "status": "PENDING"
}
```

Seed verification requires an authenticated principal with the `admin` role.

### `GET /status/{task_id}`

Returns task status and progress for a previously started ingestion task.

### `GET /health`

Returns service liveness:

```json
{ "status": "ok" }
```

## JSON Contract

The stable output contract lives in:

```text
output/schemas.py
```

It mirrors the WebApp contract:

```text
caishui-webapp/types/pipeline.ts
```

When changing `PipelineOutput`, `ChunkOutput`, or `TaxMetadata`, update both sides in the same change.

Important identity fields:

- `ChunkOutput.chunk_id`: pipeline stable source-position ID; saved by WebApp as `pipeline_chunk_id`.
- `ChunkOutput.document_id`: source document ID supplied by the caller.
- `ChunkOutput.content_hash`: SHA-256 of normalized chunk content.

Do not confuse pipeline `chunk_id` with WebApp `KnowledgeChunk.id` CUID.

## Database Ownership

Prisma migrations are owned by `caishui-webapp`.

Pipeline DB models are mirrors for runtime reads/writes only:

```text
db/models.py
```

Rules:

- Do not introduce Alembic in this service.
- Do not call SQLAlchemy `create_all`.
- Keep `ingest_tasks` DDL owned by Prisma/manual migration SQL in the WebApp repo.
- Use `db/schema_check.py` to detect drift at startup.

## Verification and Embedding Rules

- New chunks start as `unverified`.
- `seed` and `human` are the only MVP verification methods that can produce retrievable content.
- `auto` is reserved for future work and must not be emitted in MVP.
- `rejected` chunks may be stored for audit and pipeline improvement, but must not receive production embeddings.
- Only `verification_status == "verified"` chunks may call the embedding API.
- Embedding failure must not mutate verification status.

## Development Notes

- Keep orchestration in `ingestion.py`.
- Keep chunk lifecycle behavior in `chunk_lifecycle.py`.
- Keep embedding lifecycle behavior in `output/embedding_lifecycle.py`.
- Keep `output/writer.py` thin.
- Add tests around public behavior before refactoring internals.
