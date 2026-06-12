"""Ingest Task Status Read Adapter.

Status route exposes a stable task progress projection while the underlying
storage remains the Prisma-owned ingest_tasks table.
"""

from __future__ import annotations

from typing import Protocol


class TaskStatusRepository(Protocol):
    async def get_ingest_task(self, task_id: str) -> dict | None: ...


async def get_task_status(
    repository: TaskStatusRepository,
    task_id: str,
) -> dict | None:
    task = await repository.get_ingest_task(task_id)
    if not task:
        return None
    total = task["total_chunks"]
    return {
        **task,
        "progress": task["completed_chunks"] / total if total else 0,
    }
