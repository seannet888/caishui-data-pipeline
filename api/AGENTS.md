# AGENTS.md

Local rules for FastAPI route Adapters.

## Route Adapter Rules

- Routes should be thin HTTP/BackgroundTasks Adapters.
- Require signed pipeline principal for protected routes.
- Do not perform embedding eligibility, verification policy, or lifecycle branching inside route handlers.
- Delegate ingestion to `ingestion.py`.
- Delegate embedding jobs to `embedding_job.py`.
- Delegate response schemas to `output/schemas.py`.

## Error and Task Semantics

- `/ingest` starts a task for an existing WebApp-owned `source_document`.
- `/ingest` must not create the parent SourceDocument.
- `/status/{task_id}` must expose the task id and WebApp-owned document id so WebApp can perform accepted-task readiness checks.
- Background task failures must persist diagnosable task status/error information.
