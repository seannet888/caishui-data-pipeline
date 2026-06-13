from datetime import UTC, datetime

from db.ingestion_adapter import PostgresIngestionAdapter
from ingestion import IngestionChunk


def test_chunk_timestamp_params_are_naive_for_prisma_timestamp_columns():
    adapter = PostgresIngestionAdapter(
        session_factory=None,  # type: ignore[arg-type]
        task_id="task-1",
        document_id="doc-1",
    )
    chunk = IngestionChunk(
        pipeline_chunk_id="pipeline-chunk-1",
        document_id="doc-1",
        chunk_index=0,
        chunk_type="text",
        content="第一条 测试内容",
        content_hash="hash",
        metadata={"doc_type": "notice"},
        embedding_last_attempt_at=datetime(2026, 6, 13, tzinfo=UTC),
        verified_at=datetime(2026, 6, 13, tzinfo=UTC),
    )

    params = adapter._params(chunk)

    assert params["created_at"].tzinfo is None
    assert params["updated_at"].tzinfo is None
    assert params["embedding_last_attempt_at"].tzinfo is None
    assert params["verified_at"].tzinfo is None
