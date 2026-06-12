from copy import deepcopy
from datetime import UTC, datetime

from chunk_lifecycle import reconcile_chunk
from ingestion import IngestionChunk


def chunk(*, content_hash: str) -> IngestionChunk:
    return IngestionChunk(
        pipeline_chunk_id="location-1",
        document_id="doc-1",
        chunk_index=0,
        chunk_type="text",
        content="财税条款内容",
        content_hash=content_hash,
        metadata={},
    )


def test_changed_content_creates_clean_unverified_version():
    current = chunk(content_hash="a" * 64)
    current.row_id = "current-row"
    current.verification_status = "verified"
    current.verification_method = "human"
    current.verified_by = "reviewer-1"
    current.verified_at = datetime.now(UTC)
    current.embedding = [0.25] * 1024
    current.embedding_status = "COMPLETED"
    current.embedding_attempts = 1

    candidate = chunk(content_hash="b" * 64)
    before = deepcopy(candidate)

    decision = reconcile_chunk(candidate, current)

    assert decision.action == "create_version"
    assert decision.previous_row_id == "current-row"
    assert candidate == before
    assert candidate.row_id is None
    assert candidate.verification_status == "unverified"
    assert candidate.embedding is None
    assert candidate.embedding_status == "PENDING"
