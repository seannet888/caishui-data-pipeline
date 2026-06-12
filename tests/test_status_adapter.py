from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from db.status_adapter import get_task_status


class RecordingStatusRepository:
    def __init__(self, row):
        self.row = row
        self.task_ids: list[str] = []

    async def get_ingest_task(self, task_id: str):
        self.task_ids.append(task_id)
        return self.row


def test_status_adapter_projects_task_progress_from_ingest_task_row():
    repository = RecordingStatusRepository(
        {
            "task_id": "task-1",
            "document_id": "doc-1",
            "status": "PROCESSING",
            "completed_chunks": 2,
            "total_chunks": 5,
            "error_message": None,
            "created_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
            "started_at": None,
            "completed_at": None,
            "updated_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
        }
    )

    result = asyncio.run(get_task_status(repository, "task-1"))

    assert repository.task_ids == ["task-1"]
    assert result == {
        "task_id": "task-1",
        "document_id": "doc-1",
        "status": "PROCESSING",
        "completed_chunks": 2,
        "total_chunks": 5,
        "error_message": None,
        "created_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
        "started_at": None,
        "completed_at": None,
        "updated_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
        "progress": 0.4,
    }


def test_status_adapter_returns_none_when_task_does_not_exist():
    repository = RecordingStatusRepository(None)

    result = asyncio.run(get_task_status(repository, "missing-task"))

    assert result is None
