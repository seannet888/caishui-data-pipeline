from __future__ import annotations

import asyncio

from db.ingestion_adapter import PostgresIngestionAdapter
from output.schemas import PipelineOutput


class RecordingSession:
    def __init__(self) -> None:
        self.executions: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def begin(self):
        return self

    async def execute(self, _statement, params):
        self.executions.append(params)


class RecordingSessionFactory:
    def __init__(self) -> None:
        self.session = RecordingSession()

    def __call__(self):
        return self.session


def test_completed_maps_partial_failure_to_failed_task_status():
    session_factory = RecordingSessionFactory()
    adapter = PostgresIngestionAdapter(
        session_factory=session_factory,
        task_id="task-partial",
        document_id="doc-partial",
    )

    asyncio.run(
        adapter.completed(
            PipelineOutput(
                task_id="task-partial",
                document_id="doc-partial",
                status="partial_failure",
                total_chunks=2,
                errors=["chunk-1:embedding provider rejected input"],
            )
        )
    )

    task_update = session_factory.session.executions[0]
    document_update = session_factory.session.executions[2]
    assert task_update["task_status"] == "FAILED"
    assert document_update["document_status"] == "FAILED"
    assert task_update["error_message"] == "chunk-1:embedding provider rejected input"
